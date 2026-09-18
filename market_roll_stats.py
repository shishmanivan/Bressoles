"""Persistent audit of actual market RNG samples, shared across profiles.

The append-only journal is authoritative; the small summary is rebuildable.
No calls to the game's random generator are made here.
"""

import csv
from datetime import datetime, timezone
import logging
import os
from uuid import uuid4

from csv_storage import write_semicolon_csv_atomically


ROLLS_FILE = "MarketRolls.csv"
SUMMARY_FILE = "MarketRollSummary.csv"
OUTCOMES = {"rise": "Рост", "fall": "Падение", "flat": "Флет"}
PROBABILITY_FIELDS = {
    "rise": "ВероятностьРоста%",
    "fall": "ВероятностьПадения%",
    "flat": "ВероятностьФлета%",
}
FIELDS = [
    "БросокID", "ВремяUTC", "Профиль", "ТестовыйРежим", "Уровень", "Раунд", "День",
    "Акция", "Результат", "ВероятностьРезультата%",
    *PROBABILITY_FIELDS.values(), "СлучайноеЧисло0до100",
]
SUMMARY_FIELDS = [
    "Выборка", "Профиль", "Акция", "Результат", "ВероятностьГруппы%",
    "СлучайныхБросков", "Фактически", "Ожидалось", "Фактически%", "Ожидалось%",
    "РазницаПП",
]


class MarketRollStats:
    def __init__(self, rolls_file=ROLLS_FILE, summary_file=SUMMARY_FILE):
        self.rolls_file = rolls_file
        self.summary_file = summary_file
        self._signature = None
        self._groups = {}

    def _file_signature(self):
        try:
            stat = os.stat(self.rolls_file)
            return stat.st_size, stat.st_mtime_ns
        except FileNotFoundError:
            return 0, 0

    def _add_rows(self, rows):
        for row in rows:
            for outcome, label in OUTCOMES.items():
                probability = float(row[PROBABILITY_FIELDS[outcome]])
                for scope, profile in (("Общая", ""), ("Профиль", row["Профиль"])):
                    # Include every eligible trial in each direction's denominator,
                    # including trials where that direction had probability zero.
                    for group_probability in ("Все", str(probability)):
                        key = scope, profile, row["Акция"], label, group_probability
                        totals = self._groups.setdefault(key, [0, 0, 0.0])
                        totals[0] += 1
                        totals[1] += int(row["Результат"] == label)
                        totals[2] += probability / 100

    def _load_if_changed(self):
        signature = self._file_signature()
        if self._signature == signature:
            return
        self._groups = {}
        if signature[0]:
            with open(self.rolls_file, encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, delimiter=";")
                if reader.fieldnames != FIELDS:
                    raise ValueError("Unexpected market roll journal schema")
                self._add_rows(reader)
        self._signature = signature

    def rebuild_summary(self):
        """Recreate the report from the journal, also after restarting the game."""
        self._load_if_changed()
        rows = []
        for key, (count, actual, expected) in sorted(self._groups.items()):
            actual_percent = 100 * actual / count
            expected_percent = 100 * expected / count
            rows.append(dict(zip(SUMMARY_FIELDS, (
                *key, count, actual, round(expected, 6), round(actual_percent, 6),
                round(expected_percent, 6), round(actual_percent - expected_percent, 6),
            ))))
        write_semicolon_csv_atomically(self.summary_file, SUMMARY_FIELDS, rows)

    def record(self, rolls, *, profile_slot=None, level="", round_num="", day="", test_mode=False):
        if not rolls:
            return
        batch_id = uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        rows = []
        for roll in rolls:
            probs = roll["probabilities"]
            outcome = roll["outcome"]
            rows.append({
                "БросокID": batch_id,
                "ВремяUTC": timestamp,
                "Профиль": str(profile_slot) if profile_slot is not None else "Без профиля",
                "ТестовыйРежим": int(test_mode),
                "Уровень": level,
                "Раунд": round_num,
                "День": day,
                "Акция": "ABC"[roll["market"]],
                "Результат": OUTCOMES[outcome],
                "ВероятностьРезультата%": probs[outcome],
                **{field: probs[key] for key, field in PROBABILITY_FIELDS.items()},
                "СлучайноеЧисло0до100": roll["random_value"],
            })
        try:
            self._load_if_changed()
            needs_header = self._signature[0] == 0
            os.makedirs(os.path.dirname(self.rolls_file) or ".", exist_ok=True)
            with open(self.rolls_file, "a", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=FIELDS, delimiter=";")
                if needs_header:
                    writer.writeheader()
                writer.writerows(rows)
                target.flush()
                os.fsync(target.fileno())
            self._add_rows(rows)
            self._signature = self._file_signature()
            self.rebuild_summary()
        except (OSError, ValueError, csv.Error):
            # In particular, Excel may lock the report on Windows. Never reroll
            # or append the same batch again if the journal was already saved.
            self._signature = None
            logging.getLogger(__name__).exception("Не удалось сохранить статистику рыночных бросков")


if __name__ == "__main__":
    MarketRollStats().rebuild_summary()
