import math
import random

import game_state
from game_data import (
    get_level_rounds_required,
    load_levels_config,
    load_rounds_config,
)


# Boss difficulty tiers. Watt is the test/easy boss; tier 2 bosses appear on
# Level 4's second boss step.
BOSS_LEVELS = {
    "1_Watt.png": 0,
    "2_AdamSmith.png": 1,
    "3_RobertFulton.png": 1,
    "4_NicolasApper.png": 1,
    "5_SamuelSlater.png": 1,
    "6_Arkwright.png": 1,
    "7_Kolbe.png": 1,
    "8_List.png": 2,
    "Laffitte.png": 2,
}

BOSS_NUMBERS = {
    "Laffitte.png": 9,
}


def get_bosses_for_boss_level(boss_level: int):
    """Return all boss filenames assigned to a boss difficulty tier."""
    try:
        normalized_level = int(boss_level)
    except (TypeError, ValueError):
        return []
    return [filename for filename, level in BOSS_LEVELS.items() if level == normalized_level]


def _build_level4_default_roster():
    """Fallback Level 4 roster: first step uses level-1 bosses, second uses level-2 bosses."""
    level_one_bosses = get_bosses_for_boss_level(1)
    level_two_bosses = get_bosses_for_boss_level(2)
    if not level_one_bosses and not level_two_bosses:
        return []

    roster = []
    if level_one_bosses:
        roster.append(level_one_bosses[:2])
    if level_two_bosses:
        roster.append(level_two_bosses[:2])

    remaining = level_one_bosses[2:]
    roster.extend([[boss_filename] for boss_filename in remaining])
    return roster


# Boss roster per level and boss rounds
LEVEL_BOSS_ROUNDS = {
    1: [["1_Watt.png"]],
    2: [["2_AdamSmith.png", "3_RobertFulton.png"],
        ["4_NicolasApper.png", "5_SamuelSlater.png"]],
    4: _build_level4_default_roster(),
}

# -------------------------------
# Level 3 dynamic boss roster
# -------------------------------
def _generate_level3_boss_roster(bosses_required: int):
    """Level 3: pick N distinct bosses from the level-3 pool, shuffled, with no player choice."""
    candidates = [
        "2_AdamSmith.png",
        "3_RobertFulton.png",
        "4_NicolasApper.png",
        "5_SamuelSlater.png",
        "6_Arkwright.png",
        "7_Kolbe.png",
    ]
    random.shuffle(candidates)
    try:
        n = int(bosses_required or 0)
    except (TypeError, ValueError):
        n = 0
    n = max(1, min(n, len(candidates)))
    chosen = candidates[:n]
    return [[fn] for fn in chosen]


def _ensure_level3_roster(bp_state: dict, bosses_required: int):
    """Ensure bp_state has a stable roster for the current Level 3 run (and matches bosses_required)."""
    roster = bp_state.get("roster")
    if isinstance(roster, list) and roster and len(roster) == max(1, int(bosses_required or 1)):
        return roster
    roster = _generate_level3_boss_roster(bosses_required)
    bp_state["roster"] = roster
    return roster


# -------------------------------
# Level 4 dynamic boss roster
# -------------------------------
def _generate_level4_boss_roster(bosses_required: int):
    """Level 4: first step offers level-1 bosses, second step offers level-2 bosses."""
    level_one_bosses = get_bosses_for_boss_level(1)
    level_two_bosses = get_bosses_for_boss_level(2)
    random.shuffle(level_one_bosses)
    random.shuffle(level_two_bosses)
    try:
        n = int(bosses_required or 0)
    except (TypeError, ValueError):
        n = 0
    n = max(1, n)

    if not level_one_bosses and not level_two_bosses:
        return []

    roster = []
    if level_one_bosses:
        roster.append(level_one_bosses[: min(2, len(level_one_bosses))])
    if len(roster) < n and level_two_bosses:
        roster.append(level_two_bosses[: min(2, len(level_two_bosses))])

    remaining = level_one_bosses[min(2, len(level_one_bosses)) :]

    while len(roster) < n:
        if not remaining:
            remaining = get_bosses_for_boss_level(1)
            random.shuffle(remaining)
        roster.append([remaining.pop(0)])

    return roster


def _ensure_level4_roster(bp_state: dict, bosses_required: int):
    """Ensure bp_state has a stable roster for the current Level 4 run."""
    roster = bp_state.get("roster")
    expected_len = max(1, int(bosses_required or 1))
    level_two_bosses = set(get_bosses_for_boss_level(2))
    current_second_step = set(roster[1] or []) if isinstance(roster, list) and len(roster) > 1 else set()
    has_level_two_step = (
        isinstance(roster, list)
        and len(roster) > 1
        and bool(level_two_bosses)
        and level_two_bosses.issubset(current_second_step)
    )
    if isinstance(roster, list) and roster and len(roster) == expected_len and has_level_two_step:
        return roster
    roster = _generate_level4_boss_roster(bosses_required)
    bp_state["roster"] = roster
    return roster

def apper_goal_boost(goal_value, multiplier=1.3):
    """Boost goal by multiplier and round UP to tens.

    Example: 50 -> 65 -> 70
    """
    if goal_value is None:
        return None
    try:
        g = float(goal_value)
    except (TypeError, ValueError):
        return goal_value
    boosted = g * float(multiplier)
    return int(math.ceil(boosted / 10.0) * 10)


def get_boss_selection_from_filename(level_number, boss_filename):
    """
    Determine boss choice index (0/1/...) within the current boss list from boss filename.
    
    Note: `LEVEL_BOSS_ROUNDS[level]` is a list of boss-lists (one list per boss "step"/round index),
    and each boss-list can contain multiple bosses to choose from. This function returns the index
    INSIDE that boss-list (e.g. Adam=0, Fulton=1), not the outer round index.
    
    IMPORTANT (Level 2 goals): GoalsLevel2.csv uses (0/1) to select the STAGE of the level
    (before first boss vs before second boss), NOT which boss was chosen. Do not use this value
    to select GoalsLevel2.csv columns.
    
    Args:
        level_number: Level number
        boss_filename: Boss filename (e.g., "2_AdamSmith.png")
    
    Returns:
        Boss selection index (0..n-1) or 0 if not found
    """
    if level_number != 2 or not boss_filename:
        return 0
    
    bosses_for_level = LEVEL_BOSS_ROUNDS.get(level_number, [])
    for round_index, boss_list in enumerate(bosses_for_level):
        if boss_filename in boss_list:
            try:
                return boss_list.index(boss_filename)
            except ValueError:
                return 0
    return 0


def get_bosses_required(level_num, rounds_config):
    """Return bosses required for a level (PRIMARY: LevelsData.csv).

    Fallback order:
    1) LevelsData.csv
    2) RoundsData.csv (legacy)
    3) roster length (LEVEL_BOSS_ROUNDS)
    4) default 1
    """
    levels_config = load_levels_config()
    cfg_val = (levels_config.get(level_num, {}) or {}).get("Bosses")
    if cfg_val and cfg_val > 0:
        return cfg_val

    cfg_val = rounds_config.get(level_num, {}).get("Bosses") if rounds_config else None
    if cfg_val and cfg_val > 0:
        return cfg_val
    roster = LEVEL_BOSS_ROUNDS.get(level_num)
    if roster:
        return max(1, len(roster))
    return 1


def get_configured_levels(rounds_config, levels_config=None):
    """Return sorted list of level numbers that have Rounds > 0 (PRIMARY: LevelsData.csv)."""
    levels_config = levels_config if levels_config is not None else load_levels_config()

    candidates = set()
    for lvl in (levels_config or {}).keys():
        candidates.add(lvl)
    for lvl in (rounds_config or {}).keys():
        candidates.add(lvl)

    out = []
    for level in candidates:
        r = get_level_rounds_required(level, rounds_config=rounds_config, levels_config=levels_config)
        if r is not None and r > 0:
            out.append(level)
    return sorted(out)


def validate_levels_and_rounds_config():
    """
    Validate levels and rounds configuration (LevelsData.csv primary, with legacy fallback).
    Logs warnings for missing/inconsistent data. Call at startup.
    """
    rounds_config = load_rounds_config()
    levels_config = load_levels_config()
    configured = get_configured_levels(rounds_config, levels_config=levels_config)
    errors = []
    # Levels with bosses must have Rounds configured
    for level in LEVEL_BOSS_ROUNDS:
        r = get_level_rounds_required(level, rounds_config=rounds_config, levels_config=levels_config)
        if r is None or r <= 0:
            errors.append(
                f"Level {level} has bosses (LEVEL_BOSS_ROUNDS) but no valid 'Rounds' in LevelsData.csv (or legacy RoundsData.csv)."
            )
        elif level not in configured:
            errors.append(
                f"Level {level} has Rounds={r} but was not in configured levels list (internal check)."
            )
    # Warn about configured levels without bosses (optional; not an error)
    for level in configured:
        if level not in LEVEL_BOSS_ROUNDS:
            print(
                f"VALIDATE levels/rounds: Level {level} has Rounds configured but no LEVEL_BOSS_ROUNDS (no bosses)."
            )
    for msg in errors:
        print(f"VALIDATE levels/rounds: {msg}")
    return len(errors) == 0


def apply_boss_reward(reward_string, gameplay_instance):
    """Apply boss reward from reward string.
    Example: "Dobor=Dobor+1" -> global_dobor += 1 and gameplay_instance.Dobor += 1
    For Money rewards (e.g., "Money=Money+2"), this function updates both the current
    GameplayPage.Money and the global_start_money_bonus so that future rounds start
    with the increased amount.
    
    Args:
        reward_string: Reward string from BossRewards.csv (e.g., "Dobor=Dobor+1")
        gameplay_instance: GameplayPage instance to apply the reward to
    """
    if not reward_string or not gameplay_instance:
        return
    
    try:
        reward_parts = [part.strip() for part in str(reward_string).split(",") if part.strip()]
        if len(reward_parts) > 1:
            for reward_part in reward_parts:
                apply_boss_reward(reward_part, gameplay_instance)
            return

        # Special reward: RedCard (pick a random available red card and force it into starting hand)
        if str(reward_string).strip().lower() == "redcard":
            level_num = getattr(gameplay_instance, "level_number", None)
            red_card = game_state.draw_red_card_for_level(int(level_num or 0))
            if red_card is None:
                print(f"WARNING: RedCard reward requested but no available red cards pool for level {level_num}.")
                return

            forced = game_state.forced_start_hand_cards_by_level.setdefault(int(level_num or 0), [])
            if red_card not in forced:
                forced.append(red_card)

            # Also show it in reward UI if applicable
            try:
                if hasattr(gameplay_instance, "last_earned_cards") and isinstance(gameplay_instance.last_earned_cards, list):
                    gameplay_instance.last_earned_cards.append(red_card)
            except Exception:
                pass

            print(f"Applied boss reward RedCard: forced starting-hand card for level {level_num}: {red_card}")
            return

        normalized_reward = str(reward_string).strip().replace(" ", "").replace("_", "").replace("-", "").lower()
        if normalized_reward.startswith("guaranteeredstart"):
            level_num = int(getattr(gameplay_instance, "level_number", 0) or 0)
            count = 2
            if "=" in str(reward_string):
                try:
                    count = int(str(reward_string).split("=", 1)[1].strip())
                except (TypeError, ValueError):
                    count = 2
            selected = game_state.guarantee_existing_red_start_cards(level_num, count)
            print(
                f"Applied boss reward GuaranteeRedStart={count}: "
                f"guaranteed existing red cards for level {level_num}: {selected}"
            )
            return

        if normalized_reward in ("freeshop", "nextshopfree", "shopfree", "shopdiscount100"):
            game_state.set_pending_shop_discount(100)
            print("Applied boss reward FreeShop: next shop is free")
            return

        if normalized_reward in (
            "updownplus4",
            "updownsideplus4",
            "upsideanddownsideplus4",
            "upside_downside_plus4",
            "upside/downside+4",
            "probabilitycardsplus4",
        ):
            game_state.add_updown_probability_bonus(4)
            print("Applied boss reward UpDownPlus4: Upside/Downside bonus increased by 4")
            return

        # Special reward: GainDropCard (pick a random available Gain/Drop card for the level deck)
        if normalized_reward in (
            "gaindropcard",
            "randomgaindrop",
            "randomgaindropcard",
        ):
            level_num = int(getattr(gameplay_instance, "level_number", 0) or 0)
            gain_drop_card = game_state.pick_random_gain_drop_card(excluded_card_ids={13, 14})
            if gain_drop_card is None:
                print("WARNING: GainDropCard reward requested but no available Gain/Drop cards pool.")
                return

            game_state.earned_reward_cards.setdefault(level_num, []).append(gain_drop_card)

            try:
                if hasattr(gameplay_instance, "last_earned_cards") and isinstance(gameplay_instance.last_earned_cards, list):
                    gameplay_instance.last_earned_cards.append(gain_drop_card)
            except Exception:
                pass

            print(f"Applied boss reward GainDropCard: card for level {level_num}: {gain_drop_card}")
            return

        # Special reward: SilverCard (pick a random available silver card for the persistent inventory)
        if normalized_reward in (
            "silvercard",
            "randomsilver",
            "randomsilvercard",
            "randsilver",
        ):
            level_num = int(getattr(gameplay_instance, "level_number", 0) or 0)
            silver_card = game_state.add_silver_card(level_num=level_num)
            if silver_card is None:
                print("WARNING: SilverCard reward requested but no available silver cards pool.")
                return

            try:
                if hasattr(gameplay_instance, "last_earned_cards") and isinstance(gameplay_instance.last_earned_cards, list):
                    gameplay_instance.last_earned_cards.append(silver_card)
            except Exception:
                pass

            print(f"Applied boss reward SilverCard: card {silver_card}")
            return

        # Parse format: "VariableName=VariableName+1" or "VariableName=VariableName-1"
        if '=' in reward_string:
            left, right = reward_string.split('=', 1)
            var_name = left.strip()
            
            # Check if right side matches pattern: "VariableName+number" or "VariableName-number"
            if right.strip().startswith(var_name):
                operation = right.strip()[len(var_name):]
                
                if operation.startswith('+'):
                    # Addition: "Dobor+1" -> Dobor += 1
                    try:
                        amount = int(operation[1:].strip())
                        if hasattr(gameplay_instance, var_name):
                            current_value = getattr(gameplay_instance, var_name)
                            new_value = current_value + amount
                            setattr(gameplay_instance, var_name, new_value)
                            # Update global variables for special cases
                            if var_name == "Dobor":
                                # Persist Dobor across future rounds
                                game_state.global_dobor = new_value
                            elif var_name == "Money":
                                # Persist bonus to starting Money across future rounds
                                # Add the amount to the existing bonus, don't replace it
                                game_state.global_start_money_bonus += amount
                            elif var_name == "LastTurn":
                                game_state.global_last_turn_bonus += amount
                            elif var_name == "hand":
                                game_state.global_hand_bonus += amount
                            print(f"Applied boss reward: {var_name} = {current_value} + {amount} = {new_value}")
                        else:
                            print(f"WARNING: Variable {var_name} not found in gameplay instance")
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid reward format: {reward_string}")
                elif operation.startswith('-'):
                    # Subtraction: "Dobor-1" -> Dobor -= 1
                    try:
                        amount = int(operation[1:].strip())
                        if hasattr(gameplay_instance, var_name):
                            current_value = getattr(gameplay_instance, var_name)
                            new_value = current_value - amount
                            setattr(gameplay_instance, var_name, new_value)
                            # Update global variables for special cases
                            if var_name == "Dobor":
                                game_state.global_dobor = new_value
                            elif var_name == "Money":
                                # Subtract the amount from the existing bonus
                                game_state.global_start_money_bonus -= amount
                            elif var_name == "LastTurn":
                                game_state.global_last_turn_bonus -= amount
                            elif var_name == "hand":
                                game_state.global_hand_bonus -= amount
                            print(f"Applied boss reward: {var_name} = {current_value} - {amount} = {new_value}")
                        else:
                            print(f"WARNING: Variable {var_name} not found in gameplay instance")
                    except (TypeError, ValueError):
                        print(f"WARNING: Invalid reward format: {reward_string}")
                else:
                    print(f"WARNING: Unsupported reward operation: {reward_string}")
            else:
                # Direct assignment: "VariableName=value"
                try:
                    value = int(right.strip())
                    if hasattr(gameplay_instance, var_name):
                        setattr(gameplay_instance, var_name, value)
                        # Update global variables for special cases
                        if var_name == "Dobor":
                            game_state.global_dobor = value
                        elif var_name == "Money":
                            game_state.global_start_money_bonus = value
                        elif var_name == "hand":
                            game_state.global_hand_bonus = value - 7
                        print(f"Applied boss reward: {var_name} = {value}")
                    else:
                        print(f"WARNING: Variable {var_name} not found in gameplay instance")
                except (TypeError, ValueError):
                    print(f"WARNING: Invalid reward format: {reward_string}")
        else:
            print(f"WARNING: Invalid reward format (no '=' found): {reward_string}")
    except Exception as e:
        print(f"ERROR applying boss reward '{reward_string}': {e}")


def apply_boss_functionality(func_string, gameplay_instance):
    """Apply boss functionality from functionality string.
    Example: "Self.hand=Self.hand-1" -> gameplay_instance.hand -= 1
    Example: "LastTurn=LastTurn-1" -> gameplay_instance.LastTurn -= 1
    
    Args:
        func_string: Functionality string from BossRewards.csv (e.g., "Self.hand=Self.hand-1")
        gameplay_instance: GameplayPage instance to apply the functionality to
    """
    if not func_string or not gameplay_instance:
        return
    
    try:
        func_parts = [part.strip() for part in str(func_string).split(",") if part.strip()]
        if len(func_parts) > 1:
            for func_part in func_parts:
                apply_boss_functionality(func_part, gameplay_instance)
            return

        normalized_func = str(func_string).strip().replace(" ", "").replace("_", "").replace("-", "").lower()
        if normalized_func in ("arkwrightstealshares", "stealshares", "sharesteal"):
            setattr(gameplay_instance, "boss_steals_shares", True)
            print("Applied boss functionality: Arkwright share theft enabled")
            return

        if normalized_func in ("oddturntradingonly", "kolbeoddturntrading", "tradingoddturnsonly"):
            setattr(gameplay_instance, "boss_odd_turn_trading_only", True)
            print("Applied boss functionality: odd-turn trading only enabled")
            return

        if normalized_func in (
            "noprice2buys",
            "nobuyprice2",
            "cannotbuyprice2",
            "forbidprice2buys",
            "blockprice2buys",
        ):
            setattr(gameplay_instance, "boss_forbid_price_2_buys", True)
            print("Applied boss functionality: buying stocks priced at 2 is disabled")
            return

        if normalized_func in ("simplestockbot", "stockbot", "bot"):
            setattr(gameplay_instance, "stock_bot_enabled", False)
            print("Skipped Simple stock bot functionality: stock bot is only enabled for Friedrich List")
            return

        if normalized_func in ("liststockbot", "friedrichliststockbot", "listbot"):
            level_num = int(getattr(gameplay_instance, "level_number", 0) or 0)
            boss_number = None
            try:
                if hasattr(gameplay_instance, "_get_active_boss_number"):
                    boss_number = gameplay_instance._get_active_boss_number()
            except Exception:
                boss_number = None
            if level_num == 4 and boss_number == 8:
                setattr(gameplay_instance, "stock_bot_enabled", True)
                setattr(gameplay_instance, "stock_bot_type", "simple")
                setattr(
                    gameplay_instance,
                    "stock_bot_start_quantities",
                    {"Aquantity": 0, "Bquantity": 10, "Cquantity": 0},
                )
                print("Applied boss functionality: Friedrich List stock bot enabled")
            else:
                setattr(gameplay_instance, "stock_bot_enabled", False)
                print(f"Skipped Friedrich List stock bot functionality on level {level_num}, boss {boss_number}")
            return

        if normalized_func in (
            "bot2",
            "bot2percent",
            "bot2percentage",
            "bot2procent",
            "bot2procentny",
            "bot2procentnyi",
            "bot2percentbot",
            "bot2percentagebot",
            "advancedstockbot",
            "probabilitystockbot",
            "advancedliststockbot",
            "probabilityliststockbot",
            "listprobabilitybot",
            "laffittebot",
            "laffittepercentbot",
        ):
            level_num = int(getattr(gameplay_instance, "level_number", 0) or 0)
            boss_number = None
            try:
                if hasattr(gameplay_instance, "_get_active_boss_number"):
                    boss_number = gameplay_instance._get_active_boss_number()
            except Exception:
                boss_number = None
            if level_num == 4:
                setattr(gameplay_instance, "stock_bot_enabled", True)
                setattr(gameplay_instance, "stock_bot_type", "advanced")
                start_quantities = {"Aquantity": 0, "Bquantity": 10, "Cquantity": 0}
                if boss_number == 9:
                    start_quantities = {"Aquantity": 4, "Bquantity": 0, "Cquantity": 0}
                    setattr(gameplay_instance, "boss_forbid_price_2_buys", True)
                    setattr(gameplay_instance, "stock_bot_blocked_buy_prices", {2})
                setattr(gameplay_instance, "stock_bot_start_quantities", start_quantities)
                print(f"Applied boss functionality: advanced stock bot enabled for boss {boss_number}")
            else:
                setattr(gameplay_instance, "stock_bot_enabled", False)
                print(f"Skipped advanced stock bot functionality on level {level_num}, boss {boss_number}")
            return

        if normalized_func == "goal=goal*1.3":
            print("Applied boss functionality: Apper goal multiplier is handled by goal resolution")
            return

        if '=' not in func_string:
            print(f"WARNING: Invalid functionality format (no '=' found): {func_string}")
            return
        
        left, right = func_string.split('=', 1)
        var_name = left.strip()
        right = right.strip()
        
        # Handle "Self." prefix - remove it to get the actual variable name
        if var_name.startswith("Self."):
            var_name = var_name[5:]  # Remove "Self." prefix
        
        # Check if it's an operation (e.g., "hand-1") or direct assignment
        if '+' in right or '-' in right:
            # Operation: "VariableName+1" or "VariableName-1"
            if '+' in right:
                parts = right.split('+')
                operation = '+'
            else:
                parts = right.split('-')
                operation = '-'
            
            if len(parts) != 2:
                print(f"WARNING: Invalid functionality format: {func_string}")
                return
            
            var_ref = parts[0].strip()
            # Remove "Self." prefix if present
            if var_ref.startswith("Self."):
                var_ref = var_ref[5:]
            
            try:
                amount = int(parts[1].strip())
                if hasattr(gameplay_instance, var_name):
                    current_value = getattr(gameplay_instance, var_name)
                    if operation == '+':
                        new_value = current_value + amount
                    else:  # operation == '-'
                        new_value = current_value - amount
                        # Ensure hand doesn't go below 1
                        if var_name == "hand" and new_value < 1:
                            new_value = 1
                            print(f"WARNING: Hand size cannot be less than 1, clamping to 1")
                    setattr(gameplay_instance, var_name, new_value)
                    print(f"Applied boss functionality: {var_name} = {current_value} {operation} {amount} = {new_value}")
                else:
                    print(f"WARNING: Variable {var_name} not found in gameplay instance")
            except (TypeError, ValueError):
                print(f"WARNING: Invalid functionality format: {func_string}")
        else:
            # Direct assignment: "VariableName=value"
            try:
                value = int(right.strip())
                if hasattr(gameplay_instance, var_name):
                    setattr(gameplay_instance, var_name, value)
                    print(f"Applied boss functionality: {var_name} = {value}")
                else:
                    print(f"WARNING: Variable {var_name} not found in gameplay instance")
            except (TypeError, ValueError):
                print(f"WARNING: Invalid functionality format: {func_string}")
    except Exception as e:
        print(f"ERROR applying boss functionality '{func_string}': {e}")


def get_boss_number_from_filename(boss_filename):
    """Extract boss number from boss filename.
    Examples: "1_Watt.png" -> 1, "2_AdamSmith.png" -> 2, "4_NicolasApper.png" -> 4
    
    Args:
        boss_filename: Boss filename (e.g., "2_AdamSmith.png")
    
    Returns:
        Boss number (int) or None if not found
    """
    if not boss_filename:
        return None
    if boss_filename in BOSS_NUMBERS:
        return BOSS_NUMBERS[boss_filename]
    try:
        # Extract number from filename (format: "X_Name.png")
        parts = boss_filename.split("_")
        if parts and parts[0].isdigit():
            return int(parts[0])
    except (ValueError, AttributeError):
        pass
    return None


def get_boss_number_from_index(level_number, boss_index, defeated_count=0):
    """Get boss number from level and boss index for BossRewards.csv lookup.
    
    Args:
        level_number: Level number
        boss_index: Boss index (0-based) in current boss step
        defeated_count: Number of bosses already defeated on this level (determines which boss step we're in)
    
    Returns:
        Boss number for BossRewards.csv or None
    """
    try:
        round_index = int(defeated_count or 0)
    except (TypeError, ValueError):
        round_index = 0
    if round_index < 0:
        round_index = 0

    bosses_for_level = LEVEL_BOSS_ROUNDS.get(level_number, [])
    if round_index < len(bosses_for_level):
        boss_list = bosses_for_level[round_index] or []
        if 0 <= boss_index < len(boss_list):
            boss_filename = boss_list[boss_index]
            return get_boss_number_from_filename(boss_filename)
    return None
