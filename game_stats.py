import csv
import functools
import os

from csv_storage import write_semicolon_csv_atomically
from game_data import get_level_rounds_required, load_levels_config


STATS_FILE = "GameStats.csv"
LEVEL6_EXPERIMENT_STATS_FILE = None
_ACTIVE_STATS_FILE = None
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
    "ПорядковыйРаунд",
    "Сложность",
    "Сыграно",
    "Победы",
    "Поражения",
    "ПроцентПобед",
    "ДеньгиВсего",
    "ДеньгиСреднее",
    "ДеньгиМаксимум",
    "ДеньгиПоследние",
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
    15: "Джон Джейкоб Астор",
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


def build_sequential_round_number(
    level_number,
    round_num=None,
    boss_position=1,
    is_boss_fight=False,
    boss_number=None,
):
    """Return the ordinal stage number for every configured level route."""
    try:
        normalized_level = int(level_number or 0)
    except (TypeError, ValueError):
        return ""

    levels_config = load_levels_config()
    if normalized_level not in levels_config:
        return ""
    rounds_before_boss = get_level_rounds_required(
        normalized_level,
        levels_config=levels_config,
    )

    try:
        position = max(1, int(boss_position or 1))
    except (TypeError, ValueError):
        position = 1
    cycle_width = rounds_before_boss + 1
    cycle_start = (position - 1) * cycle_width

    if is_boss_fight:
        return str(cycle_start + cycle_width)

    try:
        local_round = int(round_num or 0)
    except (TypeError, ValueError):
        return ""
    if 1 <= local_round <= rounds_before_boss:
        return str(cycle_start + local_round)
    try:
        is_fulton = int(boss_number or 0) == 3
    except (TypeError, ValueError):
        is_fulton = False
    if local_round == rounds_before_boss + 1 and is_fulton:
        return _format_number(cycle_start + rounds_before_boss + 0.5)
    return ""


def _mirror_level6_experiment(update_function):
    """Write moved-marathon events to the primary and existing experiment logs."""
    @functools.wraps(update_function)
    def wrapped(level_number, *args, **kwargs):
        global _ACTIVE_STATS_FILE
        previous_active_file = _ACTIVE_STATS_FILE
        _ACTIVE_STATS_FILE = STATS_FILE
        try:
            result = update_function(level_number, *args, **kwargs)
        finally:
            _ACTIVE_STATS_FILE = previous_active_file

        try:
            normalized_level = int(level_number or 0)
        except (TypeError, ValueError):
            normalized_level = 0
        if normalized_level == 8 and LEVEL6_EXPERIMENT_STATS_FILE:
            _ACTIVE_STATS_FILE = LEVEL6_EXPERIMENT_STATS_FILE
            try:
                update_function(level_number, *args, **kwargs)
            finally:
                _ACTIVE_STATS_FILE = previous_active_file
        return result

    return wrapped


@_mirror_level6_experiment
def update_game_stats(
    level_number,
    boss_number,
    round_label,
    won,
    difficulty_label="",
    earned_money=None,
    sequential_round_number="",
):
    rows = _read_rows()
    level_key = str(level_number)
    boss_number_key = str(boss_number) if boss_number is not None else ""
    boss_name = get_boss_name(boss_number)
    difficulty_label = _normalize_difficulty_label(difficulty_label)
    sequential_round_number = _normalize_sequential_round_number(sequential_round_number)

    target = None
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("ПорядковыйРаунд", "") == sequential_round_number
            and row.get("Сложность", "") == difficulty_label
        ):
            target = row
            break

    if target is None:
        target = _new_stats_row(
            level_key,
            boss_number_key,
            boss_name,
            round_label,
            difficulty_label,
            sequential_round_number,
        )
        rows.append(target)

    played = _to_int(target.get("Сыграно")) + 1
    wins = _to_int(target.get("Победы")) + (1 if won else 0)
    losses = _to_int(target.get("Поражения")) + (0 if won else 1)
    win_rate = round((wins / played) * 100, 2) if played else 0
    previous_money_total = _to_number(target.get("ДеньгиВсего"))
    earned_money_value = _to_number(earned_money)
    money_total = previous_money_total + earned_money_value
    previous_money_max = _to_number(target.get("ДеньгиМаксимум"))
    money_max = max(previous_money_max, earned_money_value)
    money_average = round(money_total / played, 2) if played else 0

    target.update(
        {
            "Босс": boss_name,
            "Сложность": difficulty_label,
            "Сыграно": str(played),
            "Победы": str(wins),
            "Поражения": str(losses),
            "ПроцентПобед": _format_percent(win_rate),
            "ДеньгиВсего": _format_number(money_total),
            "ДеньгиСреднее": _format_number(money_average),
            "ДеньгиМаксимум": _format_number(money_max),
            "ДеньгиПоследние": _format_number(earned_money_value),
        }
    )
    _write_rows(rows)


@_mirror_level6_experiment
def update_arkwright_stats(
    level_number,
    boss_number,
    round_label,
    difficulty_label,
    outcome,
    sequential_round_number="",
):
    outcome_field = ARKWRIGHT_STAT_FIELDS.get(outcome)
    if not outcome_field:
        return

    rows = _read_rows()
    level_key = str(level_number)
    boss_number_key = str(boss_number) if boss_number is not None else ""
    boss_name = get_boss_name(boss_number)
    difficulty_label = _normalize_difficulty_label(difficulty_label)
    sequential_round_number = _normalize_sequential_round_number(sequential_round_number)

    target = None
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("ПорядковыйРаунд", "") == sequential_round_number
            and row.get("Сложность", "") == difficulty_label
        ):
            target = row
            break

    if target is None:
        target = _new_stats_row(
            level_key,
            boss_number_key,
            boss_name,
            round_label,
            difficulty_label,
            sequential_round_number,
        )
        rows.append(target)

    target["Босс"] = boss_name
    target["Сложность"] = difficulty_label
    target[outcome_field] = str(_to_int(target.get(outcome_field)) + 1)
    _write_rows(rows)


@_mirror_level6_experiment
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


@_mirror_level6_experiment
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


@_mirror_level6_experiment
def update_level_run_loss_stage_stats(
    level_number,
    stage_label,
    stage_number=None,
    boss_position=None,
    boss_number=None,
):
    rows = _read_rows()
    try:
        stage_number_value = int(stage_number) if stage_number is not None else None
    except (TypeError, ValueError):
        stage_number_value = None
    normalized_stage_label = str(stage_label or "")
    is_boss_stage = normalized_stage_label.lower().startswith("boss") or normalized_stage_label.startswith("Босс")
    sequential_round_number = build_sequential_round_number(
        level_number,
        round_num=None if is_boss_stage else stage_number_value,
        boss_position=stage_number_value if is_boss_stage else boss_position,
        is_boss_fight=is_boss_stage,
        boss_number=boss_number,
    )
    if stage_number_value is None:
        stage_number_key = ""
    elif is_boss_stage:
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
        sequential_round_number,
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


@_mirror_level6_experiment
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
        build_sequential_round_number(
            level_number,
            boss_position=position,
            is_boss_fight=True,
        ),
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


def set_level6_experiment_stats_file(path):
    global LEVEL6_EXPERIMENT_STATS_FILE
    LEVEL6_EXPERIMENT_STATS_FILE = path or None
    if LEVEL6_EXPERIMENT_STATS_FILE:
        ensure_stats_file(LEVEL6_EXPERIMENT_STATS_FILE)


def _get_active_stats_file(path=None):
    return path or _ACTIVE_STATS_FILE or STATS_FILE


def ensure_stats_file(path=None):
    target_path = _get_active_stats_file(path)
    stats_dir = os.path.dirname(target_path)
    if stats_dir:
        os.makedirs(stats_dir, exist_ok=True)
    if not os.path.exists(target_path):
        _write_rows([], target_path)
    elif not _has_current_schema(target_path):
        _write_rows(_read_rows(target_path), target_path)


def _has_current_schema(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as stats_file:
            return next(csv.reader(stats_file, delimiter=";"), []) == FIELDNAMES
    except OSError:
        return False


def _read_rows(path=None):
    target_path = _get_active_stats_file(path)
    if not os.path.exists(target_path):
        return []
    with open(target_path, "r", encoding="utf-8-sig", newline="") as stats_file:
        reader = csv.DictReader(stats_file, delimiter=";")
        rows = []
        for row in reader:
            if not row:
                continue
            normalized = {field: row.get(field, "") for field in FIELDNAMES}
            for field in ("ДеньгиВсего", "ДеньгиСреднее", "ДеньгиМаксимум", "ДеньгиПоследние"):
                normalized[field] = normalized.get(field) or "0"
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


def _new_stats_row(
    level_key,
    boss_number_key,
    boss_name,
    round_label,
    difficulty_label,
    sequential_round_number="",
):
    row = {
        "Уровень": level_key,
        "БоссНомер": boss_number_key,
        "Босс": boss_name,
        "Раунд": round_label,
        "ПорядковыйРаунд": _normalize_sequential_round_number(sequential_round_number),
        "Сложность": difficulty_label,
        "Сыграно": "0",
        "Победы": "0",
        "Поражения": "0",
        "ПроцентПобед": "0",
        "ДеньгиВсего": "0",
        "ДеньгиСреднее": "0",
        "ДеньгиМаксимум": "0",
        "ДеньгиПоследние": "0",
    }
    for field in ARKWRIGHT_STAT_FIELDS.values():
        row[field] = "0"
    return row


def _find_or_create_stats_row(
    rows,
    level_key,
    boss_number_key,
    boss_name,
    round_label,
    difficulty_label,
    sequential_round_number="",
):
    difficulty_label = _normalize_difficulty_label(difficulty_label)
    sequential_round_number = _normalize_sequential_round_number(sequential_round_number)
    for row in rows:
        if (
            row.get("Уровень") == level_key
            and row.get("БоссНомер") == boss_number_key
            and row.get("Раунд") == round_label
            and row.get("ПорядковыйРаунд", "") == sequential_round_number
            and row.get("Сложность", "") == difficulty_label
        ):
            row["Босс"] = boss_name
            return row
    target = _new_stats_row(
        level_key,
        boss_number_key,
        boss_name,
        round_label,
        difficulty_label,
        sequential_round_number,
    )
    rows.append(target)
    return target


def _normalize_difficulty_label(difficulty_label):
    difficulty_upper = str(difficulty_label or "").strip().upper()
    return "Boss" if difficulty_upper == "BOSS" else difficulty_upper


def _normalize_sequential_round_number(value):
    if value in (None, ""):
        return ""
    number = _to_number(value)
    if number <= 0:
        return ""
    return _format_number(number)


def _write_rows(rows, path=None):
    target_path = _get_active_stats_file(path)
    rows = sorted(rows, key=_sort_key)
    write_semicolon_csv_atomically(target_path, FIELDNAMES, rows)


def _sort_key(row):
    return (
        _to_int(row.get("Уровень")),
        _to_int(row.get("БоссНомер")),
        _to_number(row.get("ПорядковыйРаунд")) or 99_999,
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


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _format_number(value):
    rounded = round(float(value or 0), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded).rstrip("0").rstrip(".")


def _format_percent(value):
    if float(value).is_integer():
        return str(int(value))
    return str(value)
