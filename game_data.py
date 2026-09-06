import csv
import os


REWARD_TOKEN_RANDOM_RED = -1001
REWARD_TOKEN_RANDOM_SILVER = -1002

_cards_config_cache = None
_rounds_config_cache = None
_levels_config_cache = None
_goals_level2_cache = None
_goals_level3_cache = None
_goals_level4_cache = None
_goals_level5_cache = None
_goals_level6_cache = None
_goals_level8_cache = None
_rewards_config_cache = None
_boss_rewards_cache = None


def _parse_positive_int_field(row, key):
    raw = (row.get(key, "") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_nonnegative_int_field(row, key):
    raw = (row.get(key, "") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def parse_reward_card_token(token: str):
    """Parse a single Rewards.csv token into a card id or a special sentinel."""
    if token is None:
        return None
    raw = str(token).strip()
    if not raw:
        return None

    normalized = raw.replace(" ", "").replace("_", "").replace("-", "").lower()
    if normalized in ("redcard", "red"):
        return REWARD_TOKEN_RANDOM_RED
    if normalized in ("silvercard", "silver", "randsilver", "randomsilver", "randomsilvercard"):
        return REWARD_TOKEN_RANDOM_SILVER

    try:
        card_num = int(raw)
    except (TypeError, ValueError):
        return None
    if card_num == 0:
        card_num = 100
    return card_num


def load_cards_config():
    """Load card configuration from Cards.csv."""
    global _cards_config_cache
    if _cards_config_cache is not None:
        return _cards_config_cache

    config = {}
    cards_file = "Cards.csv"
    if not os.path.exists(cards_file):
        print(f"WARNING: Cards.csv not found: {cards_file}")
        _cards_config_cache = config
        return config

    try:
        with open(cards_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    card_id = int(((row.get("Card") or "").strip()) or 0)
                except (TypeError, ValueError):
                    continue
                if card_id <= 0:
                    continue

                try:
                    card_type = int(((row.get("Type") or "").strip()) or 1)
                except (TypeError, ValueError):
                    card_type = 1

                open_raw = (row.get("Open") or "").strip()
                try:
                    open_val = int(open_raw) if open_raw != "" else None
                except (TypeError, ValueError):
                    open_val = None

                variable_val = (row.get("Variable") or "").strip() or None
                config[card_id] = {"Type": card_type, "Open": open_val, "Variable": variable_val}
    except Exception as e:
        print(f"ERROR loading Cards.csv: {e}")

    _cards_config_cache = config
    return config


def load_language(lang_code="RU"):
    """Load language strings from Lang.csv and return them as a dict."""
    lang = {}

    lang_file = "Lang.csv"
    if not os.path.exists(lang_file):
        print(f"WARNING: Language file not found: {lang_file}")
        return lang

    try:
        with open(lang_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                key = row.get("Key", "").strip()
                value = row.get("RU", "").strip() if lang_code == "RU" else row.get("ENG", "").strip()
                if key:
                    lang[key] = value
    except Exception as e:
        print(f"ERROR loading language file: {e}")
        lang = {
            "MenuStart": "Start Game",
            "MenuOption": "Options",
            "MenuQuit": "Quit",
        }
    return lang


def load_levels_config():
    """Load per-level meta configuration from LevelsData.csv."""
    global _levels_config_cache
    if _levels_config_cache is not None:
        return _levels_config_cache

    config = {}
    levels_file = "LevelsData.csv"
    if not os.path.exists(levels_file):
        print(f"WARNING: LevelsData.csv not found: {levels_file}")
        _levels_config_cache = config
        return config

    try:
        with open(levels_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    level = int(row.get("Level", 0))
                except (TypeError, ValueError):
                    continue
                if level <= 0:
                    continue

                config[level] = {
                    "Rounds": _parse_nonnegative_int_field(row, "Rounds"),
                    "Bosses": _parse_positive_int_field(row, "Bosses"),
                }
    except Exception as e:
        print(f"ERROR loading LevelsData.csv: {e}")

    _levels_config_cache = config
    return config


def get_level_rounds_required(level_num, rounds_config=None, levels_config=None):
    """Return rounds required before boss for a level."""
    levels_config = levels_config if levels_config is not None else load_levels_config()
    cfg_val = (levels_config.get(level_num, {}) or {}).get("Rounds")
    if cfg_val is not None and cfg_val >= 0:
        return cfg_val

    cfg_val = rounds_config.get(level_num, {}).get("Rounds") if rounds_config else None
    if cfg_val and cfg_val > 0:
        return cfg_val

    return 1


def load_goals_level2():
    """Load goals for level 2 from GoalsLevel2.csv."""
    global _goals_level2_cache
    if _goals_level2_cache is not None:
        return _goals_level2_cache

    goals = {"E": {}, "M": {}}
    goals_file = "GoalsLevel2.csv"
    if not os.path.exists(goals_file):
        print(f"WARNING: GoalsLevel2.csv not found: {goals_file}")
        _goals_level2_cache = goals
        return goals

    try:
        with open(goals_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                button = row.get("", "").strip().upper()
                if button not in ["E", "M"]:
                    continue

                for round_num in ["1", "2", "3", "4"]:
                    value_str = row.get(round_num, "").strip()
                    if value_str:
                        try:
                            goals[button][(0, int(round_num))] = int(value_str)
                        except (TypeError, ValueError):
                            pass

                for round_num in ["1", "2", "3", "4"]:
                    col_name = f"B2_{round_num}"
                    value_str = row.get(col_name, "").strip()
                    if value_str:
                        try:
                            goals[button][(1, int(round_num))] = int(value_str)
                        except (TypeError, ValueError):
                            pass

                boss_round_str = row.get("Boss Round", "").strip()
                if boss_round_str:
                    try:
                        goals[button][(0, "boss")] = int(boss_round_str)
                    except (TypeError, ValueError):
                        pass

                boss_round2_str = row.get("Boss Round2", "").strip()
                if boss_round2_str:
                    try:
                        goals[button][(1, "boss")] = int(boss_round2_str)
                    except (TypeError, ValueError):
                        pass
    except Exception as e:
        print(f"ERROR loading GoalsLevel2.csv: {e}")

    _goals_level2_cache = goals
    return goals


def load_goals_level3():
    """Load goals for level 3 from GoalsLevel3.csv."""
    global _goals_level3_cache
    if _goals_level3_cache is not None:
        return _goals_level3_cache

    goals = {"E": {}, "M": {}, "H": {}}
    goals_file = "GoalsLevel3.csv"
    if not os.path.exists(goals_file):
        print(f"WARNING: GoalsLevel3.csv not found: {goals_file}")
        _goals_level3_cache = goals
        return goals

    try:
        with open(goals_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                button = (row.get("", "") or "").strip().upper()
                if button not in ("E", "M", "H"):
                    continue

                for key, raw in (row or {}).items():
                    if key is None:
                        continue
                    k = str(key).strip()
                    v = (raw or "").strip()
                    if not v:
                        continue

                    if k.isdigit():
                        try:
                            goals[button][int(k)] = int(v)
                        except (TypeError, ValueError):
                            pass
                        continue

                    norm = k.replace(" ", "")
                    if norm.lower().startswith("bossround"):
                        suffix = norm[len("BossRound"):]
                        if suffix.isdigit():
                            try:
                                goals[button][("boss", int(suffix))] = int(v)
                            except (TypeError, ValueError):
                                pass
    except Exception as e:
        print(f"ERROR loading GoalsLevel3.csv: {e}")

    _goals_level3_cache = goals
    return goals


def get_level3_goal(round_num, button, defeated_count, is_boss_round=False):
    """Get goal for level 3 from GoalsLevel3.csv."""
    goals = load_goals_level3()
    button_upper = (button or "").strip().upper()
    if button_upper not in goals:
        return None

    if round_num is None or is_boss_round:
        try:
            boss_idx = int(defeated_count or 0) + 1
        except (TypeError, ValueError):
            boss_idx = 1
        return goals[button_upper].get(("boss", boss_idx))

    try:
        r = int(round_num)
    except (TypeError, ValueError):
        return None
    return goals[button_upper].get(r)


def _load_staged_goals(goals_file):
    """Read regular, boss, and per-boss-position goals for levels 4 and 5."""

    goals = {"E": {}, "M": {}, "H": {}}
    if not os.path.exists(goals_file):
        print(f"WARNING: {goals_file} not found: {goals_file}")
        return goals

    try:
        with open(goals_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                button = (row.get("", "") or "").strip().upper()
                if button not in ("E", "M", "H"):
                    continue

                for key, raw in (row or {}).items():
                    if key is None:
                        continue
                    k = str(key).strip()
                    v = (raw or "").strip()
                    if not v:
                        continue

                    if k.isdigit():
                        try:
                            goals[button][int(k)] = int(v)
                        except (TypeError, ValueError):
                            pass
                        continue

                    norm = k.replace(" ", "")
                    if norm.lower().startswith("bossround"):
                        suffix = norm[len("BossRound"):]
                        if suffix.isdigit():
                            try:
                                goals[button][("boss", int(suffix))] = int(v)
                            except (TypeError, ValueError):
                                pass
                        continue

                    stage_round = norm.replace("-", "_")
                    if stage_round.upper().startswith("B") and "_" in stage_round:
                        stage_raw, round_raw = stage_round[1:].split("_", 1)
                        if stage_raw.isdigit() and round_raw.isdigit():
                            try:
                                goals[button][(int(stage_raw), int(round_raw))] = int(v)
                            except (TypeError, ValueError):
                                pass
    except Exception as e:
        print(f"ERROR loading {goals_file}: {e}")

    return goals


def _get_staged_goal(goals, round_num, button, defeated_count, is_boss_round):
    """Prefer a position-specific round goal, falling back to the shared goal."""
    button_upper = (button or "").strip().upper()
    if button_upper not in goals:
        return None

    if round_num is None or is_boss_round:
        try:
            boss_idx = int(defeated_count or 0) + 1
        except (TypeError, ValueError):
            boss_idx = 1
        return goals[button_upper].get(("boss", boss_idx))

    try:
        round_index = int(round_num)
    except (TypeError, ValueError):
        return None
    try:
        boss_idx = int(defeated_count or 0) + 1
    except (TypeError, ValueError):
        boss_idx = 1
    return goals[button_upper].get((boss_idx, round_index), goals[button_upper].get(round_index))


def load_goals_level4():
    """Load and cache goals for level 4 from GoalsLevel4.csv."""
    global _goals_level4_cache
    if _goals_level4_cache is None:
        _goals_level4_cache = _load_staged_goals("GoalsLevel4.csv")
    return _goals_level4_cache


def get_level4_goal(round_num, button, defeated_count, is_boss_round=False):
    """Get a goal for level 4 from GoalsLevel4.csv."""
    return _get_staged_goal(
        load_goals_level4(), round_num, button, defeated_count, is_boss_round,
    )


def load_goals_level5():
    """Load and cache goals for level 5 from GoalsLevel5.csv."""
    global _goals_level5_cache
    if _goals_level5_cache is None:
        _goals_level5_cache = _load_staged_goals("GoalsLevel5.csv")
    return _goals_level5_cache


def get_level5_goal(round_num, button, defeated_count, is_boss_round=False):
    """Get a goal for level 5 from GoalsLevel5.csv."""
    return _get_staged_goal(
        load_goals_level5(), round_num, button, defeated_count, is_boss_round,
    )


def load_goals_level6():
    """Load goals for level 6 from GoalsLevel6.csv."""
    global _goals_level6_cache
    if _goals_level6_cache is not None:
        return _goals_level6_cache

    goals = {"E": {}, "M": {}, "H": {}}
    goals_file = "GoalsLevel6.csv"
    if not os.path.exists(goals_file):
        print(f"WARNING: GoalsLevel6.csv not found: {goals_file}")
        _goals_level6_cache = goals
        return goals

    try:
        with open(goals_file, "r", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file, delimiter=";")
            for row in reader:
                button = (row.get("", "") or "").strip().upper()
                if button not in goals:
                    continue
                for key, raw in (row or {}).items():
                    if key is None:
                        continue
                    column = str(key).strip()
                    value = (raw or "").strip()
                    if not value:
                        continue
                    if column.isdigit():
                        goals[button][int(column)] = int(value)
                        continue
                    normalized = column.replace(" ", "")
                    if normalized.lower().startswith("bossround"):
                        suffix = normalized[len("BossRound"):]
                        if suffix.isdigit():
                            goals[button][("boss", int(suffix))] = int(value)
                        continue
                    stage_round = normalized.replace("-", "_")
                    if stage_round.upper().startswith("B") and "_" in stage_round:
                        stage_raw, round_raw = stage_round[1:].split("_", 1)
                        if stage_raw.isdigit() and round_raw.isdigit():
                            goals[button][(int(stage_raw), int(round_raw))] = int(value)
    except Exception as error:
        print(f"ERROR loading GoalsLevel6.csv: {error}")

    _goals_level6_cache = goals
    return goals


def get_level6_goal(round_num, button, defeated_count, is_boss_round=False):
    """Get a goal for level 6 from GoalsLevel6.csv."""
    goals = load_goals_level6()
    button_upper = (button or "").strip().upper()
    if button_upper not in goals:
        return None
    try:
        boss_position = int(defeated_count or 0) + 1
    except (TypeError, ValueError):
        boss_position = 1
    if round_num is None or is_boss_round:
        return goals[button_upper].get(("boss", boss_position))
    try:
        round_index = int(round_num)
    except (TypeError, ValueError):
        return None
    return goals[button_upper].get(
        (boss_position, round_index),
        goals[button_upper].get(round_index),
    )


def load_goals_level8():
    """Load the moved marathon goals from GoalsLevel8.csv."""
    global _goals_level8_cache
    if _goals_level8_cache is not None:
        return _goals_level8_cache

    goals = {"E": {}, "M": {}, "H": {}}
    goals_file = "GoalsLevel8.csv"
    if not os.path.exists(goals_file):
        print(f"WARNING: GoalsLevel8.csv not found: {goals_file}")
        _goals_level8_cache = goals
        return goals

    try:
        with open(goals_file, "r", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file, delimiter=";")
            for row in reader:
                button = (row.get("", "") or "").strip().upper()
                if button not in goals:
                    continue
                for key, raw in (row or {}).items():
                    if key is None:
                        continue
                    column = str(key).strip()
                    value = (raw or "").strip()
                    if not value:
                        continue
                    if column.isdigit():
                        goals[button][int(column)] = int(value)
                        continue
                    normalized = column.replace(" ", "")
                    if normalized.lower().startswith("bossround"):
                        suffix = normalized[len("BossRound"):]
                        if suffix.isdigit():
                            goals[button][("boss", int(suffix))] = int(value)
                        continue
                    stage_round = normalized.replace("-", "_")
                    if stage_round.upper().startswith("B") and "_" in stage_round:
                        stage_raw, round_raw = stage_round[1:].split("_", 1)
                        if stage_raw.isdigit() and round_raw.isdigit():
                            goals[button][(int(stage_raw), int(round_raw))] = int(value)
    except Exception as error:
        print(f"ERROR loading GoalsLevel8.csv: {error}")

    _goals_level8_cache = goals
    return goals


def get_level8_goal(round_num, button, defeated_count, is_boss_round=False):
    """Get a goal for the marathon now hosted on level 8."""
    goals = load_goals_level8()
    button_upper = (button or "").strip().upper()
    if button_upper not in goals:
        return None
    try:
        boss_position = int(defeated_count or 0) + 1
    except (TypeError, ValueError):
        boss_position = 1
    if round_num is None or is_boss_round:
        return goals[button_upper].get(("boss", boss_position))
    try:
        round_index = int(round_num)
    except (TypeError, ValueError):
        return None
    return goals[button_upper].get(
        (boss_position, round_index),
        goals[button_upper].get(round_index),
    )


def get_level2_goal(round_num, button, boss_selection, is_boss_round=False):
    """Get goal for level 2 based on round number, button, and boss selection."""
    round_key = "boss" if round_num is None or is_boss_round else round_num

    goals = load_goals_level2()
    button_upper = button.upper()
    if button_upper not in goals:
        return None

    return goals[button_upper].get((boss_selection, round_key))


def load_rounds_config():
    """Load per-level configuration from RoundsData.csv."""
    global _rounds_config_cache
    if _rounds_config_cache is not None:
        return _rounds_config_cache

    config = {}
    rounds_file = "RoundsData.csv"
    if not os.path.exists(rounds_file):
        print(f"WARNING: RoundsData.csv not found: {rounds_file}")
        _rounds_config_cache = config
        return config

    try:
        with open(rounds_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    level = int(row.get("Level", 0))
                except (TypeError, ValueError):
                    continue
                if level <= 0:
                    continue

                config[level] = {
                    "E": _parse_positive_int_field(row, "E"),
                    "M": _parse_positive_int_field(row, "M"),
                    "H": _parse_positive_int_field(row, "H"),
                    "Rounds": _parse_positive_int_field(row, "Rounds"),
                    "Bosses": _parse_positive_int_field(row, "Bosses"),
                }
    except Exception as e:
        print(f"ERROR loading RoundsData.csv: {e}")

    _rounds_config_cache = config
    return config


def load_rewards_config():
    """Load round rewards from Rewards.csv."""
    global _rewards_config_cache
    if _rewards_config_cache is not None:
        return _rewards_config_cache

    rewards = {}
    rewards_file = "Rewards.csv"
    if not os.path.exists(rewards_file):
        print(f"WARNING: Rewards.csv not found: {rewards_file}")
        _rewards_config_cache = rewards
        return rewards

    try:
        with open(rewards_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    level = int(row.get("Level", 0))
                    round_num = int(row.get("Round", 0))
                except (TypeError, ValueError):
                    continue

                button_val = row.get("Button") or ""
                button = button_val.strip().upper() if button_val else ""
                reward1_val = row.get("Reward1") or ""
                reward1_str = reward1_val.strip() if reward1_val else ""
                reward2_val = row.get("Reward2") or ""
                reward2_str = reward2_val.strip() if reward2_val else ""
                reward3_val = row.get("Reward3") or ""
                reward3_str = reward3_val.strip() if reward3_val else ""
                reward_text_val = row.get("Text") or ""
                reward_text = reward_text_val.strip() if reward_text_val else ""

                if level <= 0 or round_num <= 0 or not button or not reward1_str:
                    continue

                reward1_list = []
                for card_str in reward1_str.split(","):
                    card_str = card_str.strip()
                    if not card_str:
                        continue
                    token = parse_reward_card_token(card_str)
                    if token is not None:
                        reward1_list.append(token)

                if not reward1_list:
                    continue

                reward2_list = []
                if reward2_str:
                    for card_str in reward2_str.split(","):
                        card_str = card_str.strip()
                        if not card_str:
                            continue
                        token = parse_reward_card_token(card_str)
                        if token is not None:
                            reward2_list.append(token)

                reward3_list = []
                if reward3_str:
                    for card_str in reward3_str.split(","):
                        card_str = card_str.strip()
                        if not card_str:
                            continue
                        token = parse_reward_card_token(card_str)
                        if token is not None:
                            reward3_list.append(token)

                rewards[(level, round_num, button)] = {
                    "reward1": reward1_list,
                    "reward2": reward2_list if reward2_list else None,
                    "reward3": reward3_list if reward3_list else None,
                    "text": reward_text if reward_text else None,
                }
    except Exception as e:
        print(f"ERROR loading Rewards.csv: {e}")

    _rewards_config_cache = rewards
    return rewards


def load_boss_rewards():
    """Load boss rewards and functionalities from BossRewards.csv."""
    global _boss_rewards_cache
    if _boss_rewards_cache is not None:
        return _boss_rewards_cache

    rewards = {}
    rewards_file = "BossRewards.csv"
    if not os.path.exists(rewards_file):
        print(f"WARNING: BossRewards.csv not found: {rewards_file}")
        _boss_rewards_cache = rewards
        return rewards

    try:
        with open(rewards_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                boss_str = (row.get("Boss", "") or "").strip()
                reward_str = (row.get("Reward", "") or "").strip()
                func_str = (row.get("Functionalities", "") or "").strip()
                if boss_str:
                    try:
                        boss_num = int(boss_str)
                        rewards[boss_num] = {
                            "Reward": reward_str,
                            "Functionalities": func_str,
                        }
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid boss number in BossRewards.csv: {boss_str}")
    except Exception as e:
        print(f"ERROR loading BossRewards.csv: {e}")

    _boss_rewards_cache = rewards
    return rewards
