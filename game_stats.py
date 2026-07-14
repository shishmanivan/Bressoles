import csv
import os

from csv_storage import write_semicolon_csv_atomically


STATS_FILE = "GameStats.csv"
ARKWRIGHT_STAT_FIELDS = {
    "none": "АркрайтНеСыграл",
    "steal_50": "АркрайтУкрал50",
    "steal_30": "АркрайтУкрал30",
    "steal_90": "АркрайтУкрал90",
}
LEVEL_RUN_ROUND_LABEL = "Забег уровня"
LEVEL_RUN_DIFFICULTY_LABEL = "Level"
LEVEL_RUN_LOSS_STAGE_LABEL = "Поражение забега"
LEVEL_RUN_LOSS_STAGE_DIFFICULTY_LABEL = "RunLoss"
LEVEL_BOSS_ROUND_LABEL = "Босс уровня"
LEVEL_BOSS_DIFFICULTY_LABEL = "LevelBoss"
FIELDNAMES = [
    "Уровень",
    "БоссНомер",
    "Босс",
    "Раунд",
    "Сложность",
    "Сыграно",
    "Победы",
    "Поражения",
    "ПроцентПобед",
    ARKWRIGHT_STAT_FIELDS["none"],
    ARKWRIGHT_STAT_FIELDS["steal_50"],
    ARKWRIGHT_STAT_FIELDS["steal_30"],
    ARKWRIGHT_STAT_FIELDS["steal_90"],
]

BOSS_NAMES = {
    1: "Джеймс Уатт",
    2: "Адам Смит",
    3: "Роберт Фултон",
    4: "Николя Аппер",
    5: "Сэмюэль Слейтер",
    6: "Ричард Аркрайт",
    7: "Адольф Кольбе",
    8: "Фридрих Лист",
    9: "Жак Лаффит",
    10: "Роберт Стефенсон",
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


def build_difficulty_label(difficulty, is_boss_fight=False):
    if is_boss_fight:
        return "Boss"
    value = str(difficulty or "").strip().upper()
    return value if value in ("E", "M", "H") else ""


def update_game_stats(level_number, boss_number, round_label, won, difficulty_label=""):
    rows = _read_rows()
    level_key = str(level_number)
    boss_number_key = str(boss_number) if boss_number is not None else ""
    boss_name = get_boss_name(boss_number)
    difficulty_label = _normalize_difficulty_label(difficulty_label)

    target = None
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("Сложность", "") == difficulty_label
        ):
            target = row
            break

    if target is None:
        target = _new_stats_row(level_key, boss_number_key, boss_name, round_label, difficulty_label)
        rows.append(target)

    played = _to_int(target.get("Сыграно")) + 1
    wins = _to_int(target.get("Победы")) + (1 if won else 0)
    losses = _to_int(target.get("Поражения")) + (0 if won else 1)
    win_rate = round((wins / played) * 100, 2) if played else 0

    target.update(
        {
            "Босс": boss_name,
            "Сложность": difficulty_label,
            "Сыграно": str(played),
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(win_rate),
        }
    )
    _write_rows(rows)


def update_arkwright_stats(level_number, boss_number, round_label, difficulty_label, outcome):
    outcome_field = ARKWRIGHT_STAT_FIELDS.get(outcome)
    if not outcome_field:
        return

    rows = _read_rows()
    level_key = str(level_number)
    boss_number_key = str(boss_number) if boss_number is not None else ""
    boss_name = get_boss_name(boss_number)
    difficulty_label = _normalize_difficulty_label(difficulty_label)

    target = None
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("Сложность", "") == difficulty_label
        ):
            target = row
            break

    if target is None:
        target = _new_stats_row(level_key, boss_number_key, boss_name, round_label, difficulty_label)
        rows.append(target)

    target["Босс"] = boss_name
    target["Сложность"] = difficulty_label
    target[outcome_field] = str(_to_int(target.get(outcome_field)) + 1)
    _write_rows(rows)


def update_level_run_started(level_number):
    rows = _read_rows()
    target = _find_or_create_stats_row(
        rows,
        str(level_number),
        "",
        f"Уровень {int(level_number)}",
        LEVEL_RUN_ROUND_LABEL,
        LEVEL_RUN_DIFFICULTY_LABEL,
    )
    played = _to_int(target.get("Сыграно")) + 1
    wins = _to_int(target.get("Победы"))
    losses = _to_int(target.get("Поражения"))
    target.update(
        {
            "Сыграно": str(played),
            "ПроцентПобед": _format_percent(round((wins / played) * 100, 2) if played else 0),
        }
    )
    target["Поражения"] = str(losses)
    _write_rows(rows)


def update_level_run_result(level_number, won):
    rows = _read_rows()
    target = _find_or_create_stats_row(
        rows,
        str(level_number),
        "",
        f"Уровень {int(level_number)}",
        LEVEL_RUN_ROUND_LABEL,
        LEVEL_RUN_DIFFICULTY_LABEL,
    )
    played = _to_int(target.get("Сыграно"))
    if played <= 0:
        played = 1
        target["Сыграно"] = "1"
    wins = _to_int(target.get("Победы")) + (1 if won else 0)
    losses = _to_int(target.get("Поражения")) + (0 if won else 1)
    target.update(
        {
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(round((wins / played) * 100, 2) if played else 0),
        }
    )
    _write_rows(rows)


def update_level_run_loss_stage_stats(level_number, stage_label, stage_number=None):
    rows = _read_rows()
    try:
        stage_number_value = int(stage_number) if stage_number is not None else None
    except (TypeError, ValueError):
        stage_number_value = None
    normalized_stage_label = str(stage_label or "")
    if stage_number_value is None:
        stage_number_key = ""
    elif normalized_stage_label.lower().startswith("boss") or normalized_stage_label.startswith("Босс"):
        stage_number_key = f"B{stage_number_value}"
    else:
        stage_number_key = str(stage_number_value)
    target = _find_or_create_stats_row(
        rows,
        str(level_number),
        stage_number_key,
        normalized_stage_label or "Поражение",
        LEVEL_RUN_LOSS_STAGE_LABEL,
        LEVEL_RUN_LOSS_STAGE_DIFFICULTY_LABEL,
    )
    played = _to_int(target.get("Сыграно")) + 1
    losses = _to_int(target.get("Поражения")) + 1
    wins = _to_int(target.get("Победы"))
    target.update(
        {
            "Сыграно": str(played),
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(round((wins / played) * 100, 2) if played else 0),
        }
    )
    _write_rows(rows)


def update_level_boss_position_stats(level_number, boss_position, won):
    rows = _read_rows()
    position = int(boss_position or 0)
    if position <= 0:
        return
    target = _find_or_create_stats_row(
        rows,
        str(level_number),
        str(position),
        f"Босс уровня {position}",
        LEVEL_BOSS_ROUND_LABEL,
        LEVEL_BOSS_DIFFICULTY_LABEL,
    )
    played = _to_int(target.get("Сыграно")) + 1
    wins = _to_int(target.get("Победы")) + (1 if won else 0)
    losses = _to_int(target.get("Поражения")) + (0 if won else 1)
    target.update(
        {
            "Сыграно": str(played),
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(round((wins / played) * 100, 2) if played else 0),
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
        rows = []
        for row in reader:
            if not row:
                continue
            normalized = {field: row.get(field, "") for field in FIELDNAMES}
            if _is_encounter_stats_row(normalized):
                normalized["Босс"] = get_boss_name(normalized.get("БоссНомер"))
            for field in ARKWRIGHT_STAT_FIELDS.values():
                normalized[field] = normalized.get(field) or "0"
            rows.append(normalized)
        return rows


def _is_encounter_stats_row(row):
    round_label = str(row.get("Раунд") or "")
    difficulty = _normalize_difficulty_label(row.get("Сложность"))
    return (
        round_label == "Босс" or round_label.startswith("Раунд")
    ) and difficulty in ("", "E", "M", "H", "Boss")


def _new_stats_row(level_key, boss_number_key, boss_name, round_label, difficulty_label):
    row = {
        "Уровень": level_key,
        "БоссНомер": boss_number_key,
        "Босс": boss_name,
        "Раунд": round_label,
        "Сложность": difficulty_label,
        "Сыграно": "0",
        "Победы": "0",
        "Поражения": "0",
        "ПроцентПобед": "0",
    }
    for field in ARKWRIGHT_STAT_FIELDS.values():
        row[field] = "0"
    return row


def _find_or_create_stats_row(rows, level_key, boss_number_key, boss_name, round_label, difficulty_label):
    difficulty_label = _normalize_difficulty_label(difficulty_label)
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("Сложность", "") == difficulty_label
        ):
            row["Босс"] = boss_name
            return row
    target = _new_stats_row(level_key, boss_number_key, boss_name, round_label, difficulty_label)
    rows.append(target)
    return target


def _normalize_difficulty_label(difficulty_label):
    difficulty_upper = str(difficulty_label or "").strip().upper()
    return "Boss" if difficulty_upper == "BOSS" else difficulty_upper


def _write_rows(rows):
    rows = sorted(rows, key=_sort_key)
    write_semicolon_csv_atomically(STATS_FILE, FIELDNAMES, rows)


def _sort_key(row):
    return (
        _to_int(row.get("Уровень")),
        _to_int(row.get("БоссНомер")),
        _round_sort_value(row.get("Раунд")),
        _difficulty_sort_value(row.get("Сложность")),
    )


def _round_sort_value(round_label):
    if round_label == LEVEL_RUN_ROUND_LABEL:
        return -100
    if round_label == LEVEL_RUN_LOSS_STAGE_LABEL:
        return -90
    if round_label == LEVEL_BOSS_ROUND_LABEL:
        return 9_000
    if round_label == "Босс":
        return 10_000
    digits = "".join(ch for ch in str(round_label or "") if ch.isdigit())
    return _to_int(digits)


def _difficulty_sort_value(difficulty_label):
    order = {"LEVEL": -3, "RUNLOSS": -2, "LEVELBOSS": -1, "E": 0, "M": 1, "H": 2, "BOSS": 3, "": 9}
    return order.get(str(difficulty_label or "").strip().upper(), 8)


def _to_int(value):
    try:
        text = str(value or "").strip()
        if text[:1].upper() == "B" and text[1:].isdigit():
            return 1000 + int(text[1:])
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_percent(value):
    if float(value).is_integer():
        return str(int(value))
    return str(value)
