import csv
import os

import game_state
from boss_effects import parse_boss_functionality_spec, parse_boss_reward_spec
from boss_logic import BOSS_LEVELS, get_boss_number_from_filename
from card_catalog import validate_card_catalog
from game_data import (
    REWARD_TOKEN_RANDOM_RED,
    REWARD_TOKEN_RANDOM_SILVER,
    load_boss_rewards,
    load_cards_config,
    load_goals_level2,
    load_goals_level3,
    load_goals_level4,
    load_goals_level5,
    load_language,
    load_levels_config,
    load_rewards_config,
    load_rounds_config,
    parse_reward_card_token,
)
from gameplay_deck import BASE_STARTING_DECK


LEVEL_DIFFICULTIES = {
    1: ("E",),
    2: ("E", "M"),
    3: ("E", "M", "H"),
    4: ("E", "M", "H"),
    5: ("E", "M", "H"),
}

REQUIRED_LANGUAGE_KEYS = {
    "Profile",
    "MenuStart",
    "MenuOption",
    "MenuTestMode",
    "MenuQuit",
    "MainQuit",
    "PauseTitle",
    "PauseContinue",
    "PauseSaveExit",
    "PauseRestartLevel",
    "PauseRestartConfirm",
    "PauseRestartWarning",
    "PauseCancel",
    "LifecycleSelected",
    "LifecycleSilver",
    "LifecycleBlack",
    "LifecycleGold",
    "LifecycleContinue",
    "PopUpRound",
    "PopUpReward",
    "RewardWindowText",
    "RewardFinalBoss",
    "RewardLevel1FinalBoss",
    "RewardLevel2FinalBoss",
    "RewardLevel3FinalBoss",
    "RewardLevel4FinalBoss",
    "RewardLevel5FinalBoss",
    "BossVictoryDeckReset",
    "LoseWindowText",
    "LastBossReward",
    "LastBossRewardLevel5",
}
for _level_number in range(1, 5):
    REQUIRED_LANGUAGE_KEYS.add(f"Level{_level_number}Year")
for _level_number in range(1, 6):
    REQUIRED_LANGUAGE_KEYS.add(f"Level{_level_number}Cond")


def _read_csv_rows(csv_dir, filename, required_columns, key_columns, errors):
    path = os.path.join(csv_dir, filename)
    if not os.path.exists(path):
        errors.append(f"{filename}: file is missing")
        return []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file, delimiter=";")
            fieldnames = set(reader.fieldnames or [])
            missing_columns = [column for column in required_columns if column not in fieldnames]
            if missing_columns:
                errors.append(f"{filename}: missing columns {', '.join(missing_columns)}")
            rows = list(reader)
    except Exception as error:
        errors.append(f"{filename}: cannot be read: {error}")
        return []

    seen = set()
    for row_number, row in enumerate(rows, start=2):
        if row.get(None):
            errors.append(f"{filename}:{row_number}: unexpected extra columns")
        key = tuple((row.get(column) or "").strip().upper() for column in key_columns)
        if key in seen:
            errors.append(f"{filename}:{row_number}: duplicate key {key}")
        seen.add(key)
    return rows


def _validate_source_csvs(csv_dir, cards, language_keys, errors):
    _read_csv_rows(csv_dir, "Cards.csv", ("Card", "Type", "Open", "Variable"), ("Card",), errors)
    _read_csv_rows(csv_dir, "LevelsData.csv", ("Level", "Rounds", "Bosses"), ("Level",), errors)
    _read_csv_rows(
        csv_dir,
        "RoundsData.csv",
        ("Level", "E", "M", "H", "Rounds", "Bosses"),
        ("Level",),
        errors,
    )
    _read_csv_rows(
        csv_dir,
        "GoalsLevel2.csv",
        ("", "1", "2", "B2_1", "B2_2", "Boss Round", "Boss Round2"),
        ("",),
        errors,
    )
    _read_csv_rows(
        csv_dir,
        "GoalsLevel3.csv",
        ("", "1", "2", "3", "Boss Round 1", "Boss Round 2", "Boss Round3"),
        ("",),
        errors,
    )
    _read_csv_rows(
        csv_dir,
        "GoalsLevel4.csv",
        ("", "1", "2", "3", "Boss Round 1", "Boss Round 2", "Boss Round3"),
        ("",),
        errors,
    )
    _read_csv_rows(
        csv_dir,
        "GoalsLevel5.csv",
        ("", "1", "2", "3", "Boss Round 1", "Boss Round 2", "Boss Round 3", "Boss Round 4"),
        ("",),
        errors,
    )
    reward_rows = _read_csv_rows(
        csv_dir,
        "Rewards.csv",
        ("Level", "Round", "Button", "Reward1", "Reward2", "Reward3", "Text"),
        ("Level", "Round", "Button"),
        errors,
    )
    _read_csv_rows(csv_dir, "BossRewards.csv", ("Boss", "Reward", "Functionalities"), ("Boss",), errors)
    language_rows = _read_csv_rows(csv_dir, "Lang.csv", ("Key", "RU", "ENG"), ("Key",), errors)
    for row_number, row in enumerate(language_rows, start=2):
        for column in ("Key", "RU", "ENG"):
            raw_value = str(row.get(column) or "")
            if not raw_value.strip():
                errors.append(f"Lang.csv:{row_number}: {column} is empty")
            elif raw_value != raw_value.strip():
                errors.append(f"Lang.csv:{row_number}: {column} has surrounding whitespace")

    for row_number, row in enumerate(reward_rows, start=2):
        for column in ("Reward1", "Reward2", "Reward3"):
            for raw_token in str(row.get(column) or "").split(","):
                raw_token = raw_token.strip()
                if not raw_token:
                    continue
                token = parse_reward_card_token(raw_token)
                if token is None:
                    errors.append(f"Rewards.csv:{row_number}: unknown reward token '{raw_token}'")
                elif token not in (REWARD_TOKEN_RANDOM_RED, REWARD_TOKEN_RANDOM_SILVER) and token not in cards:
                    errors.append(f"Rewards.csv:{row_number}: card {token} is absent from Cards.csv")
        text_key = (row.get("Text") or "").strip()
        if text_key and text_key not in language_keys:
            errors.append(f"Rewards.csv:{row_number}: text key '{text_key}' is absent from Lang.csv")


def validate_game_content(
    *,
    cards=None,
    levels=None,
    rounds=None,
    goals_level2=None,
    goals_level3=None,
    goals_level4=None,
    goals_level5=None,
    rewards=None,
    boss_rewards=None,
    languages=None,
    csv_dir=".",
    check_source_csvs=True,
):
    cards = cards if cards is not None else load_cards_config()
    levels = levels if levels is not None else load_levels_config()
    rounds = rounds if rounds is not None else load_rounds_config()
    goals_level2 = goals_level2 if goals_level2 is not None else load_goals_level2()
    goals_level3 = goals_level3 if goals_level3 is not None else load_goals_level3()
    goals_level4 = goals_level4 if goals_level4 is not None else load_goals_level4()
    goals_level5 = goals_level5 if goals_level5 is not None else load_goals_level5()
    rewards = rewards if rewards is not None else load_rewards_config()
    boss_rewards = boss_rewards if boss_rewards is not None else load_boss_rewards()
    languages = languages if languages is not None else {
        "RU": load_language("RU"),
        "ENG": load_language("ENG"),
    }
    errors = []

    language_keys = set(languages.get("RU", {})) | set(languages.get("ENG", {}))
    if check_source_csvs:
        _validate_source_csvs(csv_dir, cards, language_keys, errors)

    for key in sorted(REQUIRED_LANGUAGE_KEYS):
        for language in ("RU", "ENG"):
            if not (languages.get(language, {}).get(key) or "").strip():
                errors.append(f"Lang.csv: {key} is missing for {language}")

    for card_id, row in cards.items():
        card_type = row.get("Type")
        if card_type not in (1, 2, 3, 4, 5):
            errors.append(f"Cards.csv: card {card_id} has unsupported Type={card_type}")
        if row.get("Open") not in (0, 1):
            errors.append(f"Cards.csv: card {card_id} must have Open=0 or Open=1")
        try:
            probability = int(row.get("Variable"))
        except (TypeError, ValueError):
            errors.append(f"Cards.csv: card {card_id} has invalid Variable={row.get('Variable')}")
        else:
            if not 0 <= probability <= 100:
                errors.append(f"Cards.csv: card {card_id} has Variable outside 0..100")

    errors.extend(
        validate_card_catalog(
            cards,
            cards_dir=os.path.join(csv_dir, "Cards"),
            check_assets=check_source_csvs,
        )
    )

    required_cards = set(BASE_STARTING_DECK)
    required_cards.update(game_state.DEFAULT_LICENSED_CARDS)
    required_cards.update(card_id for values in game_state.LICENSES_BY_LEVEL.values() for card_id in values)
    required_cards.update(card_id for values in game_state.LEVEL_COMPLETION_REWARD_CARDS.values() for card_id in values)
    required_cards.update(card_id for values in game_state.LEVEL_COMPLETION_BLACK_REWARD_CARDS.values() for card_id in values)
    for card_id in sorted(required_cards - set(cards)):
        errors.append(f"Cards.csv: required card {card_id} is missing")

    licensed_offer_ids = {
        int(card_id)
        for card_ids in game_state.LICENSES_BY_LEVEL.values()
        for card_id in card_ids
    }
    for card_id in sorted(licensed_offer_ids):
        cost = game_state.LICENSE_COSTS.get(card_id)
        if cost is None:
            errors.append(f"Shop catalog: license card {card_id} has no configured cost")
        elif cost <= 0:
            errors.append(f"Shop catalog: license card {card_id} must have a positive cost")
    for card_id in sorted(set(game_state.LICENSE_COSTS) - licensed_offer_ids):
        errors.append(f"Shop catalog: license cost for card {card_id} has no unlock level")

    for card_id, cost in sorted(game_state.SHOP_CARD_COSTS.items()):
        if card_id not in cards:
            errors.append(f"Shop catalog: offered card {card_id} is absent from Cards.csv")
        if cost <= 0:
            errors.append(f"Shop catalog: offered card {card_id} must have a positive cost")
    for offer_id, cost in sorted(game_state.SHOP_SPECIAL_COSTS.items()):
        if cost < 0:
            errors.append(f"Shop catalog: special offer '{offer_id}' has a negative cost")

    for level, difficulties in LEVEL_DIFFICULTIES.items():
        level_row = levels.get(level) or {}
        base_rounds = level_row.get("Rounds")
        bosses = level_row.get("Bosses")
        if not base_rounds or not bosses:
            errors.append(f"LevelsData.csv: level {level} requires positive Rounds and Bosses")
            continue
        maximum_round = base_rounds + (1 if level in (2, 3, 4, 5) else 0)
        for round_number in range(1, maximum_round + 1):
            for difficulty in difficulties:
                if (level, round_number, difficulty) not in rewards:
                    errors.append(
                        f"Rewards.csv: missing level {level}, round {round_number}, difficulty {difficulty}"
                    )

        if level == 1 and not (rounds.get(1) or {}).get("E"):
            errors.append("RoundsData.csv: level 1 requires an E goal")
        elif level == 2:
            for stage in range(bosses):
                for round_number in range(1, maximum_round + 1):
                    for difficulty in difficulties:
                        if goals_level2.get(difficulty, {}).get((stage, round_number)) is None:
                            errors.append(
                                f"GoalsLevel2.csv: missing stage {stage + 1}, round {round_number}, difficulty {difficulty}"
                            )
                if not any(
                    goals_level2.get(difficulty, {}).get((stage, "boss")) is not None
                    for difficulty in difficulties
                ):
                    errors.append(f"GoalsLevel2.csv: missing boss goal for position {stage + 1}")
        elif level == 3:
            for round_number in range(1, maximum_round + 1):
                for difficulty in difficulties:
                    if goals_level3.get(difficulty, {}).get(round_number) is None:
                        errors.append(
                            f"GoalsLevel3.csv: missing round {round_number}, difficulty {difficulty}"
                        )
            for position in range(1, bosses + 1):
                if not any(
                    goals_level3.get(difficulty, {}).get(("boss", position)) is not None
                    for difficulty in difficulties
                ):
                    errors.append(f"GoalsLevel3.csv: missing boss goal for position {position}")
        elif level == 4:
            for position in range(1, bosses + 1):
                for round_number in range(1, maximum_round + 1):
                    for difficulty in difficulties:
                        difficulty_goals = goals_level4.get(difficulty, {})
                        if difficulty_goals.get((position, round_number), difficulty_goals.get(round_number)) is None:
                            errors.append(
                                f"GoalsLevel4.csv: missing position {position}, round {round_number}, difficulty {difficulty}"
                            )
                if not any(
                    goals_level4.get(difficulty, {}).get(("boss", position)) is not None
                    for difficulty in difficulties
                ):
                    errors.append(f"GoalsLevel4.csv: missing boss goal for position {position}")
        elif level == 5:
            for position in range(1, bosses + 1):
                for round_number in range(1, maximum_round + 1):
                    for difficulty in difficulties:
                        difficulty_goals = goals_level5.get(difficulty, {})
                        if difficulty_goals.get((position, round_number), difficulty_goals.get(round_number)) is None:
                            errors.append(
                                f"GoalsLevel5.csv: missing position {position}, round {round_number}, difficulty {difficulty}"
                            )
                if not any(
                    goals_level5.get(difficulty, {}).get(("boss", position)) is not None
                    for difficulty in difficulties
                ):
                    errors.append(f"GoalsLevel5.csv: missing boss goal for position {position}")

    for reward_key, reward_data in rewards.items():
        for field in ("reward1", "reward2", "reward3"):
            for token in reward_data.get(field) or []:
                if token not in (REWARD_TOKEN_RANDOM_RED, REWARD_TOKEN_RANDOM_SILVER) and token not in cards:
                    errors.append(f"Rewards.csv: {reward_key} references missing card {token}")
        text_key = reward_data.get("text")
        if text_key and text_key not in language_keys:
            errors.append(f"Rewards.csv: {reward_key} references missing text '{text_key}'")

    active_boss_numbers = {get_boss_number_from_filename(filename) for filename in BOSS_LEVELS}
    active_boss_numbers.discard(None)
    for boss_number in sorted(active_boss_numbers - {1}):
        if boss_number not in boss_rewards:
            errors.append(f"BossRewards.csv: active boss {boss_number} has no entry")
    for boss_number in sorted(set(boss_rewards) - active_boss_numbers):
        errors.append(f"BossRewards.csv: boss {boss_number} has no matching boss filename")
    for boss_number, entry in sorted(boss_rewards.items()):
        try:
            parse_boss_reward_spec(entry.get("Reward"))
        except ValueError as error:
            errors.append(f"BossRewards.csv: boss {boss_number}: {error}")
        try:
            parse_boss_functionality_spec(entry.get("Functionalities"))
        except ValueError as error:
            errors.append(f"BossRewards.csv: boss {boss_number}: {error}")
    for boss_number in sorted(active_boss_numbers):
        for suffix in ("Text", "Reward"):
            key = f"Boss{boss_number}{suffix}"
            for language in ("RU", "ENG"):
                if not (languages.get(language, {}).get(key) or "").strip():
                    errors.append(f"Lang.csv: {key} is missing for {language}")

    return errors


def assert_valid_game_content(**kwargs):
    errors = validate_game_content(**kwargs)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(f"Game content validation failed:\n{details}")
    return True
