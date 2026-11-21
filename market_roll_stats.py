"""Persistent audit of actual market RNG samples, shared across profiles.

The append-only journal is authoritative; the small summary is rebuildable.
No calls to the game's random generator are made here.
"""
import disk_storage

import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import io
import logging
import os
from pathlib import Path
import struct
from threading import Lock
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


@contextmanager
def _locked(path, *, interactive):
    def open_lock():
        path.parent.mkdir(parents=True, exist_ok=True)
        return open(str(path) + ".lock", "a+b")

    with disk_storage.disk_operation(open_lock, interactive=interactive) as handle:
        disk_storage.disk_operation(lambda: disk_storage.lock_file_handle(handle, wait=True),
                                    interactive=interactive)
        yield


def _finish_pending(journal, pending):
    """Replay the fixed packet after checking how much of it reached the CSV."""
    try:
        packet = pending.read_bytes()
    except FileNotFoundError:
        return
    if len(packet) <= 8:
        raise ValueError("Incomplete market roll recovery file")
    offset, = struct.unpack_from(">Q", packet)
    payload = packet[8:]
    with journal.open("a+b") as output:
        written = output.seek(0, os.SEEK_END) - offset
        if not 0 <= written <= len(payload):
            raise ValueError("Market roll journal size conflicts with pending batch")
        output.seek(offset)
        if output.read(written) != payload[:written]:
            raise ValueError("Market roll journal tail conflicts with pending batch")
        output.write(payload[written:])
        output.flush()
        os.fsync(output.fileno())
    pending.unlink()


def _append_batch(journal, rows):
    pending = Path(str(journal) + ".pending")
    with _locked(journal, interactive=True):
        disk_storage.disk_operation(lambda: _finish_pending(journal, pending))

        def journal_end():
            try:
                source = journal.open("rb")
            except FileNotFoundError:
                return 0, ""
            with source:
                header = source.readline(4096).decode("utf-8-sig")
                if not header:
                    return 0, ""
                if next(csv.reader([header], delimiter=";")) != FIELDS:
                    raise ValueError("Unexpected market roll journal schema")
                source.seek(-1, os.SEEK_END)
                separator = "" if source.read(1) in (b"\n", b"\r") else "\r\n"
                return source.tell(), separator

        offset, separator = disk_storage.disk_operation(journal_end)
        output = io.StringIO(newline="")
        output.write(separator)
        writer = csv.DictWriter(output, FIELDS, delimiter=";")
        if not offset:
            writer.writeheader()
        writer.writerows(rows)
        payload = output.getvalue().encode("utf-8" if offset else "utf-8-sig")
        disk_storage.atomic_write(pending, struct.pack(">Q", offset) + payload)
        disk_storage.disk_operation(lambda: _finish_pending(journal, pending))


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market-summary")


class _Summary:
    def __init__(self, journal, report):
        self.journal = journal
        self.report = report
        self._groups = {}
        self._snapshot = None
        self._queue_lock = Lock()
        self._queued = None

    def schedule(self):
        # While a report is running keep at most one follow-up for newer rolls.
        with self._queue_lock:
            if self._queued is None:
                self._queued = _executor.submit(self._refresh_in_background)
            return self._queued

    def _refresh_in_background(self):
        with self._queue_lock:
            self._queued = None
        try:
            self.refresh()
        except (OSError, ValueError, csv.Error):
            logging.getLogger(__name__).exception("Не удалось обновить сводку рыночных бросков")

    def _add_rows(self, rows):
        for row in rows:
            if None in row or None in row.values():
                raise ValueError("Incomplete row in market roll journal")
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

    def refresh(self, *, rebuild=False):
        # Serialize report publishers across game windows, independently of appends.
        with _locked(self.report, interactive=False):
            with _locked(self.journal, interactive=False):
                _finish_pending(self.journal, Path(str(self.journal) + ".pending"))
                try:
                    stat = self.journal.stat()
                    snapshot = stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
                except FileNotFoundError:
                    snapshot = 0, 0, 0, 0
            old = self._snapshot
            if rebuild or old != snapshot:
                growing = old and old[:2] == snapshot[:2] and old[2] < snapshot[2]
                start = old[2] if growing and not rebuild else 0
                if not start:
                    self._groups.clear()
                # On a parse failure the next refresh must start from the header.
                self._snapshot = None
                if snapshot[2] > start:
                    self._read_groups(start, snapshot[2])
                self._snapshot = snapshot
            self._write_report()

    def _read_groups(self, start, end):
        with self.journal.open("rb") as source:
            source.seek(start)
            def lines():
                remaining = end - start
                while remaining:
                    line = source.readline(remaining)
                    if not line:
                        raise ValueError("Market roll journal shortened during summary")
                    remaining -= len(line)
                    yield line.decode("utf-8-sig")
            reader = csv.DictReader(lines(), fieldnames=FIELDS if start else None, delimiter=";")
            if reader.fieldnames != FIELDS:
                raise ValueError("Unexpected market roll journal schema")
            self._add_rows(reader)

    def _write_report(self):
        rows = []
        for key, (count, actual, expected) in sorted(self._groups.items()):
            actual_percent = 100 * actual / count
            expected_percent = 100 * expected / count
            rows.append(dict(zip(SUMMARY_FIELDS, (
                *key, count, actual, round(expected, 6), round(actual_percent, 6),
                round(expected_percent, 6), round(actual_percent - expected_percent, 6),
            ))))
        write_semicolon_csv_atomically(self.report, SUMMARY_FIELDS, rows, interactive=False)


@lru_cache(maxsize=8)
def _report_for(journal, report):
    return _Summary(journal, report)


class MarketRollStats:
    def __init__(self, rolls_file=ROLLS_FILE, summary_file=SUMMARY_FILE):
        self.rolls_file = Path(rolls_file).absolute()
        self._summary = _report_for(self.rolls_file, Path(summary_file).absolute())
        self.summary_task = None

    def rebuild_summary(self):
        """Rebuild the complete CSV synchronously, including an interrupted append."""
        self._summary.refresh(rebuild=True)

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
            _append_batch(self.rolls_file, rows)
            self.summary_task = self._summary.schedule()
        except (OSError, ValueError, csv.Error):
            logging.getLogger(__name__).exception("Не удалось сохранить статистику рыночных бросков")


if __name__ == "__main__":
    MarketRollStats().rebuild_summary()
