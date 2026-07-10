import csv
import os


STATS_FILE = "ShopCardStats.csv"
FIELDNAMES = [
    "Уровень",
    "КартаНомер",
    "Карта",
    "Выпадений",
    "МагазиновСКартами",
    "ВсегоКарточныхСлотов",
    "ПроцентОтСлотов",
]


def set_shop_card_stats_file(path):
    global STATS_FILE
    STATS_FILE = path or "ShopCardStats.csv"
    ensure_shop_card_stats_file()


def ensure_shop_card_stats_file():
    stats_dir = os.path.dirname(STATS_FILE)
    if stats_dir:
        os.makedirs(stats_dir, exist_ok=True)
    if not os.path.exists(STATS_FILE):
        _write_rows([])


def record_shop_card_offers(level_number, offers, card_names=None):
    card_ids = []
    for offer in offers or []:
        if not isinstance(offer, dict) or offer.get("kind") != "card":
            continue
        try:
            card_ids.append(int(offer.get("card_id")))
        except (TypeError, ValueError):
            continue
    if not card_ids:
        return

    try:
        level_key = str(int(level_number or 0))
    except (TypeError, ValueError):
        level_key = "0"

    card_names = card_names or {}
    rows = _read_rows()
    level_rows = [row for row in rows if row.get("Уровень") == level_key]
    shops_with_cards = max((_to_int(row.get("МагазиновСКартами")) for row in level_rows), default=0) + 1
    total_slots = max((_to_int(row.get("ВсегоКарточныхСлотов")) for row in level_rows), default=0) + len(card_ids)

    for row in level_rows:
        row["МагазиновСКартами"] = str(shops_with_cards)
        row["ВсегоКарточныхСлотов"] = str(total_slots)

    for card_id in card_ids:
        card_key = str(card_id)
        target = _find_or_create_row(rows, level_key, card_key, card_names.get(card_id, f"Карта {card_id}"))
        target["Выпадений"] = str(_to_int(target.get("Выпадений")) + 1)
        target["МагазиновСКартами"] = str(shops_with_cards)
        target["ВсегоКарточныхСлотов"] = str(total_slots)

    for row in rows:
        if row.get("Уровень") == level_key:
            row["ПроцентОтСлотов"] = _format_percent(
                _to_int(row.get("Выпадений")) * 100 / total_slots if total_slots else 0
            )

    _write_rows(rows)


def _read_rows():
    if not os.path.exists(STATS_FILE):
        return []
    with open(STATS_FILE, "r", encoding="utf-8-sig", newline="") as stats_file:
        reader = csv.DictReader(stats_file, delimiter=";")
        rows = []
        for row in reader:
            if not row:
                continue
            rows.append({field: row.get(field, "") for field in FIELDNAMES})
        return rows


def _find_or_create_row(rows, level_key, card_key, card_name):
    for row in rows:
        if row.get("Уровень") == level_key and row.get("КартаНомер") == card_key:
            row["Карта"] = card_name
            return row
    target = {
        "Уровень": level_key,
        "КартаНомер": card_key,
        "Карта": card_name,
        "Выпадений": "0",
        "МагазиновСКартами": "0",
        "ВсегоКарточныхСлотов": "0",
        "ПроцентОтСлотов": "0",
    }
    rows.append(target)
    return target


def _write_rows(rows):
    rows = sorted(rows, key=lambda row: (_to_int(row.get("Уровень")), _to_int(row.get("КартаНомер"))))
    with open(STATS_FILE, "w", encoding="utf-8-sig", newline="") as stats_file:
        writer = csv.DictWriter(stats_file, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _format_percent(value):
    rounded = round(float(value or 0), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded).rstrip("0").rstrip(".")


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
