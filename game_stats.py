import csv
import os


STATS_FILE = "GameStats.csv"
FIELDNAMES = [
    "Уровень",
    "БоссНомер",
    "Босс",
    "Раунд",
    "Сыграно",
    "Победы",
    "Поражения",
    "ПроцентПобед",
]

BOSS_NAMES = {
    1: "Джеймс Уатт",
    2: "Адам Смит",
    3: "Роберт Фултон",
    4: "Николя Аппер",
    5: "Сэмюэль Слейтер",
    6: "Ричард Аркрайт",
}


def get_boss_name(boss_number):
    try:
        boss_number = int(boss_number)
    except (TypeError, ValueError):
        return "Неизвестный босс"
    return BOSS_NAMES.get(boss_number, f"Босс {boss_number}")


def build_round_label(round_num, is_boss_fight=False):
    if is_boss_fight:
        return "Босс"
    try:
        return f"Раунд {int(round_num)}"
    except (TypeError, ValueError):
        return "Раунд"


def update_game_stats(level_number, boss_number, round_label, won):
    rows = _read_rows()
    level_key = str(level_number)
    boss_number_key = str(boss_number) if boss_number is not None else ""
    boss_name = get_boss_name(boss_number)

    target = None
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
        ):
            target = row
            break

    if target is None:
        target = {
            "Уровень": level_key,
            "БоссНомер": boss_number_key,
            "Босс": boss_name,
            "Раунд": round_label,
            "Сыграно": "0",
            "Победы": "0",
            "Поражения": "0",
            "ПроцентПобед": "0",
        }
        rows.append(target)

    played = _to_int(target.get("Сыграно")) + 1
    wins = _to_int(target.get("Победы")) + (1 if won else 0)
    losses = _to_int(target.get("Поражения")) + (0 if won else 1)
    win_rate = round((wins / played) * 100, 2) if played else 0

    target.update(
        {
            "Босс": boss_name,
            "Сыграно": str(played),
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(win_rate),
        }
    )
    _write_rows(rows)


def set_stats_file(path):
    global STATS_FILE
    STATS_FILE = path or "GameStats.csv"
    ensure_stats_file()


def ensure_stats_file():
    stats_dir = os.path.dirname(STATS_FILE)
    if stats_dir:
        os.makedirs(stats_dir, exist_ok=True)
    if not os.path.exists(STATS_FILE):
        _write_rows([])


def _read_rows():
    if not os.path.exists(STATS_FILE):
        return []
    with open(STATS_FILE, "r", encoding="utf-8-sig", newline="") as stats_file:
        reader = csv.DictReader(stats_file, delimiter=";")
        return [dict(row) for row in reader if row]


def _write_rows(rows):
    rows = sorted(rows, key=_sort_key)
    with open(STATS_FILE, "w", encoding="utf-8-sig", newline="") as stats_file:
        writer = csv.DictWriter(stats_file, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _sort_key(row):
    return (
        _to_int(row.get("Уровень")),
        _to_int(row.get("БоссНомер")),
        _round_sort_value(row.get("Раунд")),
    )


def _round_sort_value(round_label):
    if round_label == "Босс":
        return 10_000
    digits = "".join(ch for ch in str(round_label or "") if ch.isdigit())
    return _to_int(digits)


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_percent(value):
    if float(value).is_integer():
        return str(int(value))
    return str(value)
