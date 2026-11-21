"""Three acquisition counters, independent of inventory and run resets."""
import disk_storage

import csv
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar

from csv_storage import write_semicolon_csv_atomically


STATS_FILE = "CardAcquisitionStats.csv"
COUNTERS = {
    "offered": "ПоказаноВМагазине",
    "purchased": "КупленоИгроком",
    "bonus": "ПолученоБонусом",
}
LEGACY_FIELDS = ["Профиль", "КартаНомер", "Карта", *COUNTERS.values()]
RESULT_ID = "ПоследнийБонусРаундаID"
FIELDNAMES = [*LEGACY_FIELDS, RESULT_ID]
_tracker = None
_round_bonuses = ContextVar("round_bonuses", default=None)


class CardAcquisitionStats:
    def __init__(self, profile_slot, card_names=None, path=STATS_FILE):
        self.profile = str(profile_slot) if profile_slot is not None else "Без профиля"
        self.card_names = dict(card_names or {})
        self.path = path

    def record(self, event, card_ids, *, result_id=None):
        ids = [int(card_id) for card_id in card_ids]
        if not ids:
            return
        field = COUNTERS[event]
        try:
            rows = {}
            if disk_storage.exists(self.path):
                with disk_storage.open_text(self.path, encoding="utf-8-sig", newline="") as source:
                    reader = csv.DictReader(source, delimiter=";")
                    if reader.fieldnames not in (LEGACY_FIELDS, FIELDNAMES):
                        raise ValueError("Unexpected card acquisition statistics schema")
                    for row in reader:
                        rows[(row["Профиль"], row["КартаНомер"])] = row
            if result_id:
                # Use the player's receipt even if other profiles have since
                # updated the aggregate row. Keep duplicate cards in this batch.
                ids = [
                    card_id for card_id in ids
                    if rows.get((self.profile, str(card_id)), {}).get(RESULT_ID) != result_id
                ]
                if not ids:
                    return
            for profile in ("Все", self.profile):
                for card_id in ids:
                    key = profile, str(card_id)
                    row = rows.setdefault(key, {
                        "Профиль": profile,
                        "КартаНомер": str(card_id),
                        "Карта": self.card_names.get(card_id, f"Карта {card_id}"),
                        **{counter: 0 for counter in COUNTERS.values()},
                    })
                    row["Карта"] = self.card_names.get(card_id, row["Карта"])
                    row[field] = int(row[field]) + 1
                    if result_id and profile == self.profile:
                        row[RESULT_ID] = result_id
            # Overall and per-profile counters commit together in one file.
            ordered = sorted(rows.values(), key=lambda row: (
                row["Профиль"] != "Все", row["Профиль"], int(row["КартаНомер"]),
            ))
            write_semicolon_csv_atomically(self.path, FIELDNAMES, ordered)
        except (OSError, ValueError, csv.Error) as error:
            logging.getLogger(__name__).exception("Не удалось сохранить статистику получения карт")
            if result_id and isinstance(error, OSError):
                # The committed round still contains this batch for the next load.
                raise


def configure_card_acquisition_stats(profile_slot, card_names=None, *, enabled=True, path=STATS_FILE):
    """Called by the app when selecting a profile or entering test mode."""
    global _tracker
    _tracker = CardAcquisitionStats(profile_slot, card_names, path) if enabled else None


@contextmanager
def collect_round_bonus_cards():
    cards = []
    token = _round_bonuses.set(cards)
    try:
        yield cards
    finally:
        _round_bonuses.reset(token)


def record_card_acquisitions(event, card_ids, *, result_id=None):
    if _tracker is not None:
        collected = _round_bonuses.get()
        if collected is not None and event == "bonus":
            collected.extend(card_ids)
        else:
            _tracker.record(event, card_ids, result_id=result_id)


def record_card_offers(offers):
    # Licenses unlock availability; specials are services, not card offers.
    record_card_acquisitions("offered", [
        offer["card_id"] for offer in offers or [] if offer.get("kind") == "card"
    ])
