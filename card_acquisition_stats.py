"""Three acquisition counters, independent of inventory and run resets."""

import csv
import logging
import os

from csv_storage import write_semicolon_csv_atomically


STATS_FILE = "CardAcquisitionStats.csv"
COUNTERS = {
    "offered": "ПоказаноВМагазине",
    "purchased": "КупленоИгроком",
    "bonus": "ПолученоБонусом",
}
FIELDNAMES = ["Профиль", "КартаНомер", "Карта", *COUNTERS.values()]
_tracker = None


class CardAcquisitionStats:
    def __init__(self, profile_slot, card_names=None, path=STATS_FILE):
        self.profile = str(profile_slot) if profile_slot is not None else "Без профиля"
        self.card_names = dict(card_names or {})
        self.path = path

    def record(self, event, card_ids):
        ids = [int(card_id) for card_id in card_ids]
        if not ids:
            return
        field = COUNTERS[event]
        try:
            rows = {}
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8-sig", newline="") as source:
                    reader = csv.DictReader(source, delimiter=";")
                    if reader.fieldnames != FIELDNAMES:
                        raise ValueError("Unexpected card acquisition statistics schema")
                    for row in reader:
                        rows[(row["Профиль"], row["КартаНомер"])] = row
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
            # Overall and per-profile counters commit together in one file.
            ordered = sorted(rows.values(), key=lambda row: (
                row["Профиль"] != "Все", row["Профиль"], int(row["КартаНомер"]),
            ))
            write_semicolon_csv_atomically(self.path, FIELDNAMES, ordered)
        except (OSError, ValueError, csv.Error):
            logging.getLogger(__name__).exception("Не удалось сохранить статистику получения карт")


def configure_card_acquisition_stats(profile_slot, card_names=None, *, enabled=True, path=STATS_FILE):
    """Called by the app when selecting a profile or entering test mode."""
    global _tracker
    _tracker = CardAcquisitionStats(profile_slot, card_names, path) if enabled else None


def record_card_acquisitions(event, card_ids):
    if _tracker is not None:
        _tracker.record(event, card_ids)


def record_card_offers(offers):
    # Licenses unlock availability; specials are services, not card offers.
    record_card_acquisitions("offered", [
        offer["card_id"] for offer in offers or [] if offer.get("kind") == "card"
    ])
