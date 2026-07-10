import random

from game_data import REWARD_TOKEN_RANDOM_SILVER, load_cards_config


# Game progress tracking.
level_1_boss_defeated = False
level_2_boss_defeated = False
level_3_boss_defeated = False

# Boss defeat tracking per level:
# {level_number: {"defeated": int, "last_rect": pygame.Rect or None, "lines": list}}
boss_progress = {}

# Persistent gameplay bonuses modified by boss rewards.
global_dobor = 1
global_start_money_bonus = 0
global_last_turn_bonus = 0
global_hand_bonus = 0
global_start_c_shares_bonus = 0

# Napoleondors are earned and spent inside the current level run.
napoleondors = 0
napoleondor_level = None

# Reward cards earned by player: {level_number: [list of card_ids]}.
# These are persistent boss-round rewards.
earned_reward_cards = {}

# Temporary reward cards earned from regular rounds. They are cleared after a
# boss victory or when the level attempt is reset.
round_reward_cards = {}

# Non-gold cards bought in shops. They persist through boss victories and are
# cleared when the current run is lost or the level is completed.
shop_deck_cards = []

# Cards removed from the current level deck by shop offers.
removed_deck_cards_by_level = {}

# Permanent-until-defeat +1 bonuses for Gain/Drop cards bought through Investment.
investment_card_bonuses = {}
profit_reward_bonus = 0
updown_probability_bonus = 0
pending_shop_discount_percent = 0
bailout_rounds_remaining = 0
active_long_investments = []
derivative_bought = False
issuer_bought_count = 0
bank_bought = False
bank_interest_base = None

SHOP_SPECIAL_COSTS = {
    "delisting": 1,
    "investment": 4,
    "trader": 0,
    "profit": 6,
    "underwriter": 4,
    "bailout": 4,
    "long": 2,
    "derivative": 8,
    "junk_bond": 2,
    "issuer": 10,
    "bank": 5,
}

LONG_MAX_ACTIVE = 2
LONG_ROUNDS_TO_PAYOUT = 4
LONG_PAYOUT = 6
JUNK_BOND_SUCCESS_CHANCE = 40
JUNK_BOND_PAYOUT = 6
LIFECYCLE_CARD_BASE_SLOTS = 3
ISSUER_MAX_PURCHASES = 2
BANK_INTEREST_PERCENT = 25
BANK_INTEREST_STEP = 0.5
BANK_MIN_INTEREST_BASE = 2.5

SHOP_CARD_COSTS = {
    17: 10,
    18: 15,
    117: 7,
    401: 15,
    402: 10,
    403: 15,
    404: 5,
    405: 15,
    406: 5,
}

DEFAULT_LICENSED_CARDS = {110, 111, 116, 201, 202, 206, 208}
LICENSE_COSTS = {
    112: 3,
    113: 5,
    114: 5,
    115: 7,
    118: 5,
    119: 7,
    120: 7,
    121: 12,
    122: 15,
    203: 5,
    204: 7,
    207: 7,
    214: 7,
    215: 7,
    217: 7,
    218: 7,
    219: 10,
    220: 10,
}
LICENSES_BY_LEVEL = {
    2: [112, 113, 114, 115],
    3: [203, 204, 207, 214, 215, 217, 218, 219, 220],
    4: [118, 119, 120, 121, 122],
}
licensed_card_ids = set(DEFAULT_LICENSED_CARDS)

# Active per-level "red cards" deck rebuilt on level selection.
active_red_cards_level = None
active_red_cards_deck = []

# Active per-level silver reward pool rebuilt lazily per attempt.
active_silver_cards_level = None
active_silver_cards_deck = []

# Forced "starting hand" cards by level, used by RedCard boss rewards.
forced_start_hand_cards_by_level = {}

# Guaranteed starting-hand cards by level, used by Apper. These cards are not
# added to the deck; they are only forced if already present in the deck.
guaranteed_start_hand_cards_by_level = {}

# Permanent cards unlocked by completing levels.
LEVEL_COMPLETION_REWARD_CARDS = {
    1: [12],
    2: [13],
    3: [110],
}
LEVEL_COMPLETION_BLACK_REWARD_CARDS = {
    3: [301],
}

# Silver cards are kept outside the regular deck. They are spent after the
# round where they were selected.
MAX_CARD_SLOTS = 8
MAX_SILVER_CARDS = MAX_CARD_SLOTS
MAX_BLACK_CARDS = MAX_CARD_SLOTS
MAX_GOLD_CARDS = MAX_CARD_SLOTS
silver_cards = []

# Black cards are permanent profile unlocks and stay equipped until the player
# removes them. Gold cards last for the current level run and are cleared after
# a defeat or after completing the level.
black_cards = []
active_black_cards = []
gold_cards = []
active_gold_cards = []
active_lifecycle_card_order = []
bear_goal_reduction_steps = 0
insurance_goal_debt = 0


def is_red_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 100 < cid < 200


def is_silver_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return cid == REWARD_TOKEN_RANDOM_SILVER or 200 < cid < 300


def is_black_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 300 < cid < 400


def is_gold_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 400 < cid < 500


def _normalize_card_id(card_id, default=None):
    try:
        return int(card_id)
    except (TypeError, ValueError):
        return int(default) if default is not None else None


def _add_card_to_inventory(inventory, max_cards, card_id, label, allow_duplicates=True):
    if len(inventory) >= max_cards:
        print(f"WARNING: {label} card inventory is full; reward skipped.")
        return None
    normalized = _normalize_card_id(card_id)
    if normalized is None:
        print(f"WARNING: Invalid {label} card id {card_id!r}; reward skipped.")
        return None
    if not allow_duplicates and normalized in inventory:
        return normalized
    inventory.append(normalized)
    return normalized


def add_silver_card(card_id=REWARD_TOKEN_RANDOM_SILVER, level_num=None):
    """Add a silver card to the persistent silver inventory."""
    if len(silver_cards) >= MAX_SILVER_CARDS:
        print("WARNING: Silver card inventory is full; reward skipped.")
        return None
    if is_random_silver_token(card_id):
        card_id = draw_silver_card_for_level(level_num)
        if card_id is None:
            print("WARNING: Silver Card reward requested but no available silver cards pool.")
            return None
    return _add_card_to_inventory(silver_cards, MAX_SILVER_CARDS, card_id, "Silver")


def add_black_card(card_id):
    """Unlock a permanent black card."""
    return _add_card_to_inventory(black_cards, MAX_BLACK_CARDS, card_id, "Black", allow_duplicates=False)


def add_gold_card(card_id):
    """Add a gold card for the current run. Intended to be called by the shop."""
    normalized = _normalize_card_id(card_id)
    if normalized is None or is_shop_card_already_bought(normalized):
        return None
    return _add_card_to_inventory(gold_cards, MAX_GOLD_CARDS, normalized, "Gold")


def get_bought_shop_card_ids():
    bought = set()
    for card_id in list(shop_deck_cards or []) + list(gold_cards or []):
        normalized = _normalize_card_id(card_id)
        if normalized is not None:
            bought.add(normalized)
    return bought


def is_shop_card_already_bought(card_id):
    normalized = _normalize_card_id(card_id)
    return normalized is not None and normalized in get_bought_shop_card_ids()


def normalize_license_ids(card_ids=None):
    result = set(DEFAULT_LICENSED_CARDS)
    for card_id in card_ids or []:
        try:
            result.add(int(card_id))
        except (TypeError, ValueError):
            continue
    return result


def get_legacy_open_license_ids():
    cfg = load_cards_config() or {}
    result = set(DEFAULT_LICENSED_CARDS)
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if not is_red_card(cid) and not is_silver_card(cid):
            continue
        try:
            is_open = int(row.get("Open") if isinstance(row, dict) else 0) == 1
        except (TypeError, ValueError):
            is_open = False
        if is_open:
            result.add(cid)
    return result


def is_card_licensed(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return cid in licensed_card_ids


def unlock_card_license(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    if cid in licensed_card_ids:
        return False
    licensed_card_ids.add(cid)
    return True


def get_license_cost(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return None
    return LICENSE_COSTS.get(cid)


def get_card_pool_probability(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return None
    cfg = load_cards_config() or {}
    row = cfg.get(cid) or cfg.get(str(cid))
    if not isinstance(row, dict):
        return None
    try:
        return max(0, min(100, int(row.get("Variable", 100))))
    except (TypeError, ValueError):
        return 100


def get_card_rarity_label(card_id):
    probability = get_card_pool_probability(card_id)
    if probability is None or probability >= 50:
        return ""
    if probability >= 20:
        return "Rare"
    if probability >= 10:
        return "Very rare"
    return "Extremely rare"


def build_license_offer_pool(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    if is_level_completed(level):
        return []
    pool = []
    eligible_levels = [unlock_level for unlock_level in sorted(LICENSES_BY_LEVEL) if level >= int(unlock_level)]
    ordered_levels = []
    if level in eligible_levels:
        ordered_levels.append(level)
    ordered_levels.extend(unlock_level for unlock_level in eligible_levels if unlock_level != level)
    for unlock_level in ordered_levels:
        for card_id in LICENSES_BY_LEVEL.get(unlock_level, []):
            if not is_card_licensed(card_id):
                pool.append(int(card_id))
    random.shuffle(pool)
    return pool


def is_level_completed(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return False
    if level == 1:
        return bool(level_1_boss_defeated)
    if level == 2:
        return bool(level_2_boss_defeated)
    if level == 3:
        return bool(level_3_boss_defeated)
    return False


def add_shop_card_to_level(level_number, card_id):
    """Buy a card from the shop: gold cards go to inventory, regular cards persist for the run."""
    normalized = _normalize_card_id(card_id)
    if normalized is None:
        return None
    if is_shop_card_already_bought(normalized):
        print(f"WARNING: Shop card {normalized} was already bought this run; duplicate skipped.")
        return None
    if is_gold_card(normalized):
        return add_gold_card(normalized)
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    if level <= 0:
        return None
    shop_deck_cards.append(normalized)
    print(f"Bought shop card {normalized}; persistent shop deck={shop_deck_cards}")
    return normalized


def clear_shop_deck_cards(reason="defeat"):
    if shop_deck_cards:
        print(f"Cleared shop-bought cards after {reason}: {shop_deck_cards}")
    shop_deck_cards.clear()


def is_random_silver_token(card_id):
    try:
        return int(card_id) == REWARD_TOKEN_RANDOM_SILVER
    except (TypeError, ValueError):
        return False


def has_silver_cards():
    return bool(silver_cards)


def has_selectable_lifecycle_cards():
    return bool(silver_cards or black_cards or gold_cards)


def clear_gold_cards(reason="defeat"):
    global bear_goal_reduction_steps
    if gold_cards:
        cleared = list(gold_cards)
        gold_cards.clear()
        print(f"Cleared gold cards after {reason}: {cleared}")
    if active_gold_cards:
        active_gold_cards.clear()
        print(f"Cleared active gold cards after {reason}.")
    _sync_active_lifecycle_card_order()
    bear_goal_reduction_steps = 0


def set_active_black_cards(selected_cards):
    """Persist equipped black cards until the player removes them."""
    active_black_cards.clear()
    available = list(black_cards or [])
    slot_limit = get_lifecycle_card_slot_limit()
    if slot_limit <= 0:
        return list(active_black_cards)
    for card_id in selected_cards or []:
        normalized = _normalize_card_id(card_id)
        if normalized is None:
            continue
        try:
            available.remove(normalized)
        except ValueError:
            continue
        active_black_cards.append(normalized)
        if len(active_black_cards) >= slot_limit:
            break
    return list(active_black_cards)


def set_active_gold_cards(selected_cards):
    """Persist equipped gold cards, preserving duplicate-card inventory counts."""
    active_gold_cards.clear()
    available = list(gold_cards or [])
    slot_limit = max(0, get_lifecycle_card_slot_limit() - len(active_black_cards))
    if slot_limit <= 0:
        return list(active_gold_cards)
    for card_id in selected_cards or []:
        normalized = _normalize_card_id(card_id)
        if normalized is None:
            continue
        try:
            available.remove(normalized)
        except ValueError:
            continue
        active_gold_cards.append(normalized)
        if len(active_gold_cards) >= slot_limit:
            break
    return list(active_gold_cards)


def _normalize_lifecycle_order_entry(entry):
    if isinstance(entry, dict):
        kind = entry.get("kind")
        card_id = entry.get("card_id", entry.get("id"))
    elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
        kind, card_id = entry[0], entry[1]
    else:
        return None
    kind = str(kind or "").lower()
    if kind not in ("black", "gold"):
        return None
    normalized = _normalize_card_id(card_id)
    if normalized is None:
        return None
    return kind, normalized


def _sync_active_lifecycle_card_order(preferred_order=None):
    preferred_order = list(preferred_order or [])
    active_lifecycle_card_order.clear()
    available = {
        "black": list(active_black_cards or []),
        "gold": list(active_gold_cards or []),
    }
    for entry in preferred_order or []:
        normalized = _normalize_lifecycle_order_entry(entry)
        if normalized is None:
            continue
        kind, card_id = normalized
        try:
            available[kind].remove(card_id)
        except ValueError:
            continue
        active_lifecycle_card_order.append({"kind": kind, "card_id": card_id})

    for kind in ("black", "gold"):
        for card_id in available[kind]:
            active_lifecycle_card_order.append({"kind": kind, "card_id": card_id})

    del active_lifecycle_card_order[get_lifecycle_card_slot_limit() :]
    return list(active_lifecycle_card_order)


def set_active_lifecycle_card_order(selected_order):
    """Remember mixed black/gold active-card positions between rounds."""
    return _sync_active_lifecycle_card_order(selected_order)


def _count_card_instances(cards, target_card_id):
    count = 0
    for card_id in cards or []:
        try:
            if int(card_id) == int(target_card_id):
                count += 1
        except (TypeError, ValueError):
            continue
    return count


def get_bear_goal_discount_percent(active_cards=None):
    bear_count = _count_card_instances(active_gold_cards if active_cards is None else active_cards, 401)
    if bear_count <= 0:
        return 0
    try:
        completed_steps = max(0, int(bear_goal_reduction_steps or 0))
    except (TypeError, ValueError):
        completed_steps = 0
    return min(100, 2 * (completed_steps + 1) * bear_count)


def record_bear_victory(active_cards=None):
    global bear_goal_reduction_steps
    if _count_card_instances(active_gold_cards if active_cards is None else active_cards, 401) <= 0:
        return False
    bear_goal_reduction_steps += 1
    print(f"Bear victory progress increased: next reduction step={bear_goal_reduction_steps + 1}")
    return True


def get_insurance_goal_debt():
    try:
        return max(0, int(insurance_goal_debt or 0))
    except (TypeError, ValueError):
        return 0


def add_insurance_goal_debt(amount):
    global insurance_goal_debt
    try:
        shortfall = max(0, int(amount or 0))
    except (TypeError, ValueError):
        shortfall = 0
    if shortfall <= 0:
        return get_insurance_goal_debt()
    insurance_goal_debt = get_insurance_goal_debt() + shortfall
    print(f"Insurance carried {shortfall} goal debt forward: total={insurance_goal_debt}")
    return insurance_goal_debt


def consume_insurance_goal_debt():
    global insurance_goal_debt
    debt = get_insurance_goal_debt()
    insurance_goal_debt = 0
    if debt:
        print(f"Insurance goal debt applied to the next regular round: {debt}")
    return debt


def clear_insurance_goal_debt():
    global insurance_goal_debt
    if get_insurance_goal_debt():
        print(f"Cleared Insurance goal debt after defeat: {insurance_goal_debt}")
    insurance_goal_debt = 0


def get_bailout_rounds_remaining():
    try:
        return max(0, int(bailout_rounds_remaining or 0))
    except (TypeError, ValueError):
        return 0


def is_bailout_active():
    return get_bailout_rounds_remaining() > 0


def buy_bailout(rounds=5):
    global bailout_rounds_remaining
    try:
        duration = max(0, int(rounds or 0))
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        return 0
    bailout_rounds_remaining = duration
    print(f"Bailout activated for {bailout_rounds_remaining} round(s).")
    return bailout_rounds_remaining


def get_bailout_goal_discount_percent():
    return 20 if is_bailout_active() else 0


def apply_bailout_goal_modifier(goal_value):
    discount_percent = get_bailout_goal_discount_percent()
    if discount_percent <= 0 or goal_value is None:
        return goal_value
    try:
        base_goal = float(goal_value)
    except (TypeError, ValueError):
        return goal_value
    if base_goal <= 0:
        return goal_value
    return max(1, int(base_goal * (100 - discount_percent) / 100))


def advance_bailout_round():
    global bailout_rounds_remaining
    remaining = get_bailout_rounds_remaining()
    if remaining <= 0:
        bailout_rounds_remaining = 0
        return 0
    bailout_rounds_remaining = remaining - 1
    print(f"Bailout round consumed: remaining={bailout_rounds_remaining}")
    return bailout_rounds_remaining


def clear_bailout_bonus():
    global bailout_rounds_remaining
    if get_bailout_rounds_remaining():
        print(f"Cleared Bailout bonus: {bailout_rounds_remaining}")
    bailout_rounds_remaining = 0


def get_active_long_investments():
    active = []
    for rounds_remaining in active_long_investments or []:
        try:
            remaining = int(rounds_remaining)
        except (TypeError, ValueError):
            continue
        if remaining > 0:
            active.append(remaining)
    return active[:LONG_MAX_ACTIVE]


def is_long_offer_available():
    return len(get_active_long_investments()) < LONG_MAX_ACTIVE


def buy_long_investment(rounds=LONG_ROUNDS_TO_PAYOUT):
    active_long_investments[:] = get_active_long_investments()
    if len(active_long_investments) >= LONG_MAX_ACTIVE:
        return False
    try:
        duration = max(1, int(rounds or 0))
    except (TypeError, ValueError):
        duration = LONG_ROUNDS_TO_PAYOUT
    active_long_investments.append(duration)
    print(f"Long investment activated: active={active_long_investments}")
    return True


def advance_long_investments(level_number):
    active = get_active_long_investments()
    if not active:
        active_long_investments[:] = []
        return 0

    remaining_active = []
    matured_count = 0
    for rounds_remaining in active:
        next_remaining = int(rounds_remaining) - 1
        if next_remaining <= 0:
            matured_count += 1
        else:
            remaining_active.append(next_remaining)

    active_long_investments[:] = remaining_active
    if matured_count <= 0:
        print(f"Long investments advanced: active={active_long_investments}")
        return 0

    payout = matured_count * LONG_PAYOUT
    add_napoleondors(level_number, payout)
    print(
        f"Long investment payout: count={matured_count}, payout={payout}, "
        f"active={active_long_investments}"
    )
    return payout


def clear_long_investments():
    if get_active_long_investments():
        print(f"Cleared Long investments: {active_long_investments}")
    active_long_investments.clear()


def resolve_junk_bond(level_number):
    if random.randint(1, 100) > JUNK_BOND_SUCCESS_CHANCE:
        return False
    add_napoleondors(level_number, JUNK_BOND_PAYOUT)
    return True


def clear_silver_cards_deck():
    global active_silver_cards_level, active_silver_cards_deck
    if active_silver_cards_deck:
        print(f"Cleared silver card pool after defeat: {active_silver_cards_deck}")
    active_silver_cards_level = None
    active_silver_cards_deck = []


def ensure_napoleondor_level(level_number):
    global napoleondors, napoleondor_level
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = None
    if napoleondor_level != level:
        napoleondor_level = level
        napoleondors = get_starting_napoleondors_for_level(level)
    return napoleondors


def get_starting_napoleondors_for_level(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return 0
    starting_amount = 0
    if level >= 3 and level_2_boss_defeated:
        starting_amount += 2
    if level >= 4 and level_3_boss_defeated:
        starting_amount += 3
    return starting_amount


def add_napoleondors(level_number, amount):
    global napoleondors
    ensure_napoleondor_level(level_number)
    try:
        earned = float(amount or 0)
    except (TypeError, ValueError):
        earned = 0.0
    if earned <= 0:
        return napoleondors
    napoleondors += earned
    print(f"Earned {earned} napoleondor(s) on level {level_number}: balance={napoleondors}")
    return napoleondors


def spend_napoleondors(amount):
    global napoleondors
    try:
        cost = float(amount or 0)
    except (TypeError, ValueError):
        return False
    if cost <= 0 or cost > napoleondors:
        return False
    napoleondors -= cost
    return True


def reset_napoleondors(level_number=None):
    global napoleondors, napoleondor_level
    if level_number is not None:
        try:
            napoleondor_level = int(level_number or 0)
        except (TypeError, ValueError):
            napoleondor_level = None
    napoleondors = get_starting_napoleondors_for_level(napoleondor_level)
    print(f"Reset napoleondors for level {napoleondor_level}")


def spend_silver_cards(selected_cards):
    """Consume selected silver cards after a played round ends."""
    spent = []
    for card_id in selected_cards or []:
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            continue
        try:
            silver_cards.remove(normalized)
            spent.append(normalized)
        except ValueError:
            print(f"WARNING: Silver card {normalized} was selected but is no longer available.")
    if spent:
        print(f"Spent active silver cards after round: {spent}")
    return spent


def get_unavailable_red_cards(level_num):
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0
    unavailable = set()
    for card_id in get_completed_level_reward_cards():
        if is_red_card(card_id):
            unavailable.add(int(card_id))
    for card_id in earned_reward_cards.get(level, []) or []:
        if is_red_card(card_id):
            unavailable.add(int(card_id))
    for card_id in round_reward_cards.get(level, []) or []:
        if is_red_card(card_id):
            unavailable.add(int(card_id))
    for card_id in forced_start_hand_cards_by_level.get(level, []) or []:
        if is_red_card(card_id):
            unavailable.add(int(card_id))
    return unavailable


def remove_unavailable_red_cards_from_active_deck(level_num):
    global active_red_cards_deck
    unavailable = get_unavailable_red_cards(level_num)
    if unavailable:
        active_red_cards_deck = [card_id for card_id in active_red_cards_deck if int(card_id) not in unavailable]


def new_boss_progress_state():
    return {
        "defeated": 0,
        "last_rect": None,
        "lines": [],
        "defeated_bosses": [],
        "roster": None,
        "round_progress": {},
        "current_boss": None,
        "reward_checkpoint": None,
        "run_stats_started": False,
        "run_stats_finished": False,
    }


def reset_level_attempt(level_number):
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus, global_start_c_shares_bonus
    global profit_reward_bonus, updown_probability_bonus, derivative_bought, issuer_bought_count
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    global_dobor = 1
    global_start_money_bonus = 0
    global_last_turn_bonus = 0
    global_hand_bonus = 0
    global_start_c_shares_bonus = 0
    profit_reward_bonus = 0
    updown_probability_bonus = 0
    derivative_bought = False
    issuer_bought_count = 0
    reset_napoleondors(level_number)
    clear_round_reward_cards(level_number)
    clear_removed_deck_cards(level_number)
    clear_investment_card_bonuses()
    clear_pending_shop_discount()
    clear_shop_deck_cards()
    clear_gold_cards()
    clear_silver_cards_deck()
    clear_insurance_goal_debt()
    clear_bailout_bonus()
    clear_long_investments()
    clear_bank_offer()
    active_black_cards[:] = active_black_cards[:get_lifecycle_card_slot_limit()]
    active_gold_cards[:] = active_gold_cards[:max(0, get_lifecycle_card_slot_limit() - len(active_black_cards))]
    _sync_active_lifecycle_card_order(active_lifecycle_card_order)
    if level in guaranteed_start_hand_cards_by_level:
        guaranteed_start_hand_cards_by_level[level] = []
    state = new_boss_progress_state()
    boss_progress[level] = state
    return state


def complete_level_run(level_number):
    """Clear temporary run state after defeating the last boss of a level."""
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus, global_start_c_shares_bonus
    global profit_reward_bonus, updown_probability_bonus, derivative_bought, issuer_bought_count
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0

    global_dobor = 1
    global_start_money_bonus = 0
    global_last_turn_bonus = 0
    global_hand_bonus = 0
    global_start_c_shares_bonus = 0
    profit_reward_bonus = 0
    updown_probability_bonus = 0
    derivative_bought = False
    issuer_bought_count = 0

    if level in earned_reward_cards:
        cleared = list(earned_reward_cards.get(level) or [])
        earned_reward_cards[level] = []
        if cleared:
            print(f"Cleared boss reward cards after level completion: {cleared}")
    if level in forced_start_hand_cards_by_level:
        cleared = list(forced_start_hand_cards_by_level.get(level) or [])
        forced_start_hand_cards_by_level[level] = []
        if cleared:
            print(f"Cleared forced starting-hand cards after level completion: {cleared}")
    if level in guaranteed_start_hand_cards_by_level:
        cleared = list(guaranteed_start_hand_cards_by_level.get(level) or [])
        guaranteed_start_hand_cards_by_level[level] = []
        if cleared:
            print(f"Cleared guaranteed starting-hand cards after level completion: {cleared}")

    reset_napoleondors(level)
    clear_round_reward_cards(level)
    clear_removed_deck_cards(level)
    clear_investment_card_bonuses()
    clear_pending_shop_discount()
    clear_shop_deck_cards(reason="level completion")
    clear_gold_cards(reason="level completion")
    clear_silver_cards_deck()
    clear_insurance_goal_debt()
    clear_bailout_bonus()
    clear_long_investments()
    clear_bank_offer()
    active_black_cards[:] = active_black_cards[:get_lifecycle_card_slot_limit()]
    active_gold_cards[:] = active_gold_cards[:max(0, get_lifecycle_card_slot_limit() - len(active_black_cards))]
    _sync_active_lifecycle_card_order(active_lifecycle_card_order)


def capture_level2_loss_checkpoint(level_number):
    """Persist the level-2 post-boss state that survives later defeats."""
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return False
    if level != 2:
        return False

    state = boss_progress.get(level)
    if not isinstance(state, dict) or int(state.get("defeated", 0) or 0) <= 0:
        return False

    state["reward_checkpoint"] = {
        "global_dobor": int(global_dobor),
        "global_start_money_bonus": int(global_start_money_bonus),
        "global_last_turn_bonus": int(global_last_turn_bonus),
        "global_hand_bonus": int(global_hand_bonus),
        "global_start_c_shares_bonus": int(global_start_c_shares_bonus),
        "derivative_bought": bool(derivative_bought),
        "issuer_bought_count": get_issuer_bought_count(),
        "bank_bought": bool(bank_bought),
        "bank_interest_base": bank_interest_base,
        "updown_probability_bonus": int(updown_probability_bonus),
        "napoleondors": float(napoleondors),
        "napoleondor_level": napoleondor_level,
        "active_long_investments": list(get_active_long_investments()),
        "earned_reward_cards": list(earned_reward_cards.get(level, []) or []),
        "removed_deck_cards": list(removed_deck_cards_by_level.get(level, []) or []),
        "forced_start_hand_cards": list(forced_start_hand_cards_by_level.get(level, []) or []),
        "guaranteed_start_hand_cards": list(guaranteed_start_hand_cards_by_level.get(level, []) or []),
    }
    return True


def restore_level2_loss_checkpoint(level_number):
    """Restore level-2 boss progress and first-boss rewards after a defeat."""
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus, global_start_c_shares_bonus
    global derivative_bought, issuer_bought_count, bank_bought, bank_interest_base
    global napoleondors, napoleondor_level, profit_reward_bonus, updown_probability_bonus
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return False
    if level != 2:
        return False

    state = boss_progress.get(level)
    if not isinstance(state, dict) or int(state.get("defeated", 0) or 0) <= 0:
        return False

    checkpoint = state.get("reward_checkpoint")
    if not isinstance(checkpoint, dict):
        return False

    global_dobor = int(checkpoint.get("global_dobor", 1) or 1)
    global_start_money_bonus = int(checkpoint.get("global_start_money_bonus", 0) or 0)
    global_last_turn_bonus = int(checkpoint.get("global_last_turn_bonus", 0) or 0)
    global_hand_bonus = int(checkpoint.get("global_hand_bonus", 0) or 0)
    global_start_c_shares_bonus = int(checkpoint.get("global_start_c_shares_bonus", 0) or 0)
    derivative_bought = bool(checkpoint.get("derivative_bought", False))
    try:
        issuer_bought_count = max(0, min(ISSUER_MAX_PURCHASES, int(checkpoint.get("issuer_bought_count", 0) or 0)))
    except (TypeError, ValueError):
        issuer_bought_count = 0
    bank_bought = bool(checkpoint.get("bank_bought", False))
    try:
        bank_interest_base = (
            float(checkpoint.get("bank_interest_base"))
            if checkpoint.get("bank_interest_base") is not None
            else None
        )
    except (TypeError, ValueError):
        bank_interest_base = None
    updown_probability_bonus = int(checkpoint.get("updown_probability_bonus", 0) or 0)
    napoleondors = float(checkpoint.get("napoleondors", napoleondors) or 0)
    try:
        napoleondor_level = int(checkpoint.get("napoleondor_level", level))
    except (TypeError, ValueError):
        napoleondor_level = level
    earned_reward_cards[level] = list(checkpoint.get("earned_reward_cards") or [])
    removed_deck_cards_by_level[level] = list(checkpoint.get("removed_deck_cards") or [])
    forced_start_hand_cards_by_level[level] = list(checkpoint.get("forced_start_hand_cards") or [])
    guaranteed_start_hand_cards_by_level[level] = list(checkpoint.get("guaranteed_start_hand_cards") or [])
    active_long_investments[:] = [
        int(value)
        for value in (checkpoint.get("active_long_investments") or [])
        if str(value).lstrip("-").isdigit() and int(value) > 0
    ][:LONG_MAX_ACTIVE]

    state["round_progress"] = {}
    state["current_boss"] = None
    return True


def get_progress_flags():
    """Return unlock flags for the level selection screen."""
    return {
        "level_1_boss_defeated": level_1_boss_defeated,
        "level_2_boss_defeated": level_2_boss_defeated,
        "level_3_boss_defeated": level_3_boss_defeated,
    }


def get_level_completion_reward_cards(level_number):
    """Return the permanent deck reward for completing a specific level."""
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    return list(LEVEL_COMPLETION_REWARD_CARDS.get(level, []) or [])


def get_level_completion_black_reward_cards(level_number):
    """Return permanent black-card rewards for completing a specific level."""
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    return list(LEVEL_COMPLETION_BLACK_REWARD_CARDS.get(level, []) or [])


def get_completed_level_reward_cards():
    """Return permanent deck rewards from all completed levels."""
    cards = []
    if level_1_boss_defeated:
        cards.extend(get_level_completion_reward_cards(1))
    if level_2_boss_defeated:
        cards.extend(get_level_completion_reward_cards(2))
    if level_3_boss_defeated:
        cards.extend(get_level_completion_reward_cards(3))
    return cards


def get_level_removed_deck_cards(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return []
    return list(removed_deck_cards_by_level.get(level, []) or [])


def get_level_forced_start_hand_cards(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return []
    return list(forced_start_hand_cards_by_level.get(level, []) or [])


def get_level_guaranteed_start_hand_cards(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return []
    return list(guaranteed_start_hand_cards_by_level.get(level, []) or [])


def build_current_level_deck(level_number):
    from gameplay_deck import build_initial_deck

    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    return build_initial_deck(
        level,
        earned_reward_cards,
        get_completed_level_reward_cards(),
        removed_deck_cards_by_level,
        shop_deck_cards,
        round_reward_cards.get(level, []),
        get_level_forced_start_hand_cards(level),
    )


def build_permanent_level_deck(level_number):
    from gameplay_deck import build_initial_deck

    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    return build_initial_deck(
        level,
        earned_reward_cards,
        get_completed_level_reward_cards(),
        removed_deck_cards_by_level,
        shop_deck_cards,
        [],
        get_level_forced_start_hand_cards(level),
    )


def guarantee_existing_red_start_cards(level_number, count=2):
    try:
        level = int(level_number or 0)
        target_count = max(0, int(count or 0))
    except (TypeError, ValueError):
        return []
    if not level or target_count <= 0:
        return []

    deck_red_cards = []
    seen = set()
    for card_id in build_current_level_deck(level):
        if not is_red_card(card_id):
            continue
        normalized = int(card_id)
        if normalized in seen:
            continue
        seen.add(normalized)
        deck_red_cards.append(normalized)

    if not deck_red_cards:
        guaranteed_start_hand_cards_by_level[level] = []
        print(f"Apper reward found no red cards in level {level} deck.")
        return []

    deck_red_set = set(deck_red_cards)
    guaranteed_cards = guaranteed_start_hand_cards_by_level.setdefault(level, [])
    guaranteed_cards[:] = [
        int(card_id)
        for card_id in guaranteed_cards
        if is_red_card(card_id) and int(card_id) in deck_red_set
    ]

    already_forced = {
        int(card_id)
        for card_id in (forced_start_hand_cards_by_level.get(level, []) or [])
        if is_red_card(card_id) and int(card_id) in deck_red_set
    }
    already_guaranteed = {
        int(card_id)
        for card_id in guaranteed_cards
        if is_red_card(card_id) and int(card_id) in deck_red_set
    }
    already_starting = already_forced | already_guaranteed
    needed = max(0, target_count - len(already_starting))
    if needed <= 0:
        return []

    candidates = [card_id for card_id in deck_red_cards if card_id not in already_starting]
    random.shuffle(candidates)
    selected = candidates[:needed]
    guaranteed_cards.extend(card_id for card_id in selected if card_id not in guaranteed_cards)
    print(f"Apper guaranteed existing red start cards for level {level}: {selected}")
    return selected


def add_round_reward_card(level_number, card_id):
    try:
        level = int(level_number or 0)
        normalized = int(card_id)
    except (TypeError, ValueError):
        return None
    round_reward_cards.setdefault(level, []).append(normalized)
    print(f"Added temporary round reward card {normalized} to level {level}: {round_reward_cards[level]}")
    return normalized


def clear_round_reward_cards(level_number=None):
    if level_number is None:
        if round_reward_cards:
            print(f"Cleared all temporary round reward cards: {round_reward_cards}")
        round_reward_cards.clear()
        return
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return
    cards = round_reward_cards.pop(level, [])
    if cards:
        print(f"Cleared temporary round reward cards for level {level}: {cards}")


def is_gain_drop_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 11 <= cid <= 18


def get_current_gain_drop_deck_cards(level_number):
    seen = set()
    result = []
    for card_id in build_permanent_level_deck(level_number):
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            continue
        if not is_gain_drop_card(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def invest_gain_drop_card(card_id, level_number=None):
    try:
        normalized = int(card_id)
    except (TypeError, ValueError):
        return False
    if not is_gain_drop_card(normalized):
        return False
    if level_number is not None and normalized not in get_current_gain_drop_deck_cards(level_number):
        print(f"WARNING: Gain/Drop card {normalized} is not permanent in level {level_number} deck.")
        return False
    investment_card_bonuses[normalized] = int(investment_card_bonuses.get(normalized, 0) or 0) + 1
    print(f"Investment upgraded Gain/Drop card {normalized}: +{investment_card_bonuses[normalized]}")
    return True


def get_investment_bonus(card_id):
    try:
        normalized = int(card_id)
    except (TypeError, ValueError):
        return 0
    return int(investment_card_bonuses.get(normalized, 0) or 0)


def clear_investment_card_bonuses():
    if investment_card_bonuses:
        print(f"Cleared Investment upgrades after defeat: {investment_card_bonuses}")
    investment_card_bonuses.clear()


def buy_profit_bonus():
    global profit_reward_bonus
    profit_reward_bonus += 1
    print(f"Profit increased victory rewards by {profit_reward_bonus}.")
    return profit_reward_bonus


def buy_derivative_hand_bonus():
    global global_hand_bonus, derivative_bought
    if derivative_bought:
        print("Derivative hand bonus already bought this run.")
        return None
    global_hand_bonus += 1
    derivative_bought = True
    print(f"Derivative increased hand size bonus to {global_hand_bonus}.")
    return global_hand_bonus


def is_derivative_offer_available():
    return not bool(derivative_bought)


def get_issuer_bought_count():
    try:
        return max(0, min(ISSUER_MAX_PURCHASES, int(issuer_bought_count or 0)))
    except (TypeError, ValueError):
        return 0


def get_lifecycle_card_slot_limit():
    return LIFECYCLE_CARD_BASE_SLOTS + get_issuer_bought_count()


def get_issuer_offer_cost():
    bought_count = get_issuer_bought_count()
    if bought_count <= 0:
        return 10
    if bought_count == 1:
        return 15
    return None


def is_issuer_offer_available():
    return get_issuer_bought_count() < ISSUER_MAX_PURCHASES


def buy_issuer_slot():
    global issuer_bought_count
    if not is_issuer_offer_available():
        return None
    issuer_bought_count = get_issuer_bought_count() + 1
    print(f"Issuer increased lifecycle card slots to {get_lifecycle_card_slot_limit()}.")
    return get_lifecycle_card_slot_limit()


def clear_issuer_slots():
    global issuer_bought_count
    if issuer_bought_count:
        print(f"Cleared Issuer slot upgrades: {issuer_bought_count}")
    issuer_bought_count = 0
    active_black_cards[:] = active_black_cards[:get_lifecycle_card_slot_limit()]
    active_gold_cards[:] = active_gold_cards[:max(0, get_lifecycle_card_slot_limit() - len(active_black_cards))]
    _sync_active_lifecycle_card_order(active_lifecycle_card_order)


def is_bank_offer_available():
    return not bool(bank_bought)


def buy_bank_offer():
    global bank_bought
    if bank_bought:
        return False
    bank_bought = True
    print("Bank interest activated.")
    return True


def _round_bank_interest(amount):
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    steps = int(value / BANK_INTEREST_STEP)
    return steps * BANK_INTEREST_STEP


def update_bank_interest_base():
    global bank_interest_base
    if not bank_bought:
        bank_interest_base = None
        return None
    bank_interest_base = max(0.0, float(napoleondors or 0))
    print(f"Bank interest base updated: {bank_interest_base}")
    return bank_interest_base


def apply_bank_interest(level_number):
    global bank_interest_base
    if not bank_bought or bank_interest_base is None:
        return 0.0
    try:
        base = float(bank_interest_base or 0)
    except (TypeError, ValueError):
        base = 0.0
    bank_interest_base = None
    if base < BANK_MIN_INTEREST_BASE:
        return 0.0
    interest = _round_bank_interest(base * BANK_INTEREST_PERCENT / 100)
    if interest <= 0:
        return 0.0
    add_napoleondors(level_number, interest)
    print(f"Bank interest applied: base={base}, interest={interest}")
    return interest


def clear_bank_offer():
    global bank_bought, bank_interest_base
    if bank_bought or bank_interest_base is not None:
        print(f"Cleared Bank offer: bought={bank_bought}, base={bank_interest_base}")
    bank_bought = False
    bank_interest_base = None


def clear_profit_bonus():
    global profit_reward_bonus
    if profit_reward_bonus:
        print(f"Cleared Profit bonus: {profit_reward_bonus}")
    profit_reward_bonus = 0


def add_updown_probability_bonus(amount):
    global updown_probability_bonus
    try:
        bonus = int(amount or 0)
    except (TypeError, ValueError):
        bonus = 0
    if bonus <= 0:
        return updown_probability_bonus
    updown_probability_bonus += bonus
    print(f"Upside/Downside probability bonus increased to {updown_probability_bonus}.")
    return updown_probability_bonus


def get_updown_probability_bonus():
    return max(0, int(updown_probability_bonus or 0))


def clear_updown_probability_bonus():
    global updown_probability_bonus
    if updown_probability_bonus:
        print(f"Cleared Upside/Downside probability bonus: {updown_probability_bonus}")
    updown_probability_bonus = 0


def add_start_c_shares_bonus(amount):
    global global_start_c_shares_bonus
    try:
        bonus = int(amount or 0)
    except (TypeError, ValueError):
        bonus = 0
    if bonus <= 0:
        return global_start_c_shares_bonus
    global_start_c_shares_bonus += bonus
    print(f"Start C shares bonus increased to {global_start_c_shares_bonus}.")
    return global_start_c_shares_bonus


def clear_start_c_shares_bonus():
    global global_start_c_shares_bonus
    if global_start_c_shares_bonus:
        print(f"Cleared start C shares bonus: {global_start_c_shares_bonus}")
    global_start_c_shares_bonus = 0


def get_victory_napoleondor_reward(base_amount):
    try:
        base = float(base_amount or 0)
    except (TypeError, ValueError):
        base = 0.0
    return base + int(profit_reward_bonus or 0)


def get_shop_special_cost(offer_id):
    if offer_id == "profit" and int(profit_reward_bonus or 0) > 0:
        return 10
    if offer_id == "issuer":
        cost = get_issuer_offer_cost()
        return cost if cost is not None else SHOP_SPECIAL_COSTS.get(offer_id, 1)
    return SHOP_SPECIAL_COSTS.get(offer_id, 1)


def set_pending_shop_discount(percent):
    global pending_shop_discount_percent
    try:
        discount = max(0, min(100, int(percent or 0)))
    except (TypeError, ValueError):
        discount = 0
    pending_shop_discount_percent = max(int(pending_shop_discount_percent or 0), discount)
    if discount:
        print(f"Next shop prices reduced by {pending_shop_discount_percent}%.")
    return pending_shop_discount_percent


def consume_pending_shop_discount():
    global pending_shop_discount_percent
    try:
        discount = max(0, min(100, int(pending_shop_discount_percent or 0)))
    except (TypeError, ValueError):
        discount = 0
    pending_shop_discount_percent = 0
    return discount


def clear_pending_shop_discount():
    global pending_shop_discount_percent
    pending_shop_discount_percent = 0


def remove_card_from_level_deck(level_number, card_id):
    try:
        level = int(level_number or 0)
        normalized = int(card_id)
    except (TypeError, ValueError):
        return False
    current_deck = build_permanent_level_deck(level)
    if normalized not in current_deck:
        print(f"WARNING: Card {normalized} is not permanent in level {level} deck.")
        return False
    removed_deck_cards_by_level.setdefault(level, []).append(normalized)
    _remove_forced_start_hand_card(level, normalized)
    print(f"Delisted card {normalized} from level {level} deck.")
    return True


def _remove_forced_start_hand_card(level_number, card_id):
    try:
        level = int(level_number or 0)
        normalized = int(card_id)
    except (TypeError, ValueError):
        return False
    removed = False
    forced_cards = forced_start_hand_cards_by_level.get(level)
    if forced_cards:
        try:
            forced_cards.remove(normalized)
            removed = True
            print(f"Removed forced starting-hand card {normalized} from level {level}.")
        except ValueError:
            pass
    guaranteed_cards = guaranteed_start_hand_cards_by_level.get(level)
    if guaranteed_cards:
        try:
            guaranteed_cards.remove(normalized)
            removed = True
            print(f"Removed guaranteed starting-hand card {normalized} from level {level}.")
        except ValueError:
            pass
    return removed


def get_card_sale_value(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return None
    if cid == 100:
        return None
    if 1 <= cid <= 4:
        return 0.5
    if 11 <= cid <= 16:
        return 2
    if cid in (17, 18) or is_red_card(cid):
        return 3
    return None


def sell_cards_from_level_deck(level_number, card_ids):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return 0.0, []

    available_deck = build_permanent_level_deck(level)
    sold_cards = []
    total_value = 0.0
    for card_id in card_ids or []:
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            continue
        value = get_card_sale_value(normalized)
        if value is None:
            continue
        try:
            available_deck.remove(normalized)
        except ValueError:
            continue
        removed_deck_cards_by_level.setdefault(level, []).append(normalized)
        _remove_forced_start_hand_card(level, normalized)
        sold_cards.append(normalized)
        total_value += float(value)
        break

    if total_value > 0:
        add_napoleondors(level, total_value)
        print(f"Sold cards from level {level} deck: {sold_cards}; value={total_value}")
    return total_value, sold_cards


def clear_removed_deck_cards(level_number=None):
    if level_number is None:
        removed_deck_cards_by_level.clear()
        return
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        return
    removed_deck_cards_by_level.pop(level, None)


def build_shop_card_offer_pool(level_number=1):
    """Return shop-buyable card offers."""
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    if level < 4:
        return []

    bought_cards = get_bought_shop_card_ids()
    pool = []
    for card_id, chance in ((17, 5), (18, 5), (117, 50)):
        if card_id not in bought_cards and random.randint(1, 100) <= chance:
            pool.append(card_id)

    for card_id in build_gold_cards_pool():
        if card_id not in bought_cards and card_id not in pool:
            pool.append(card_id)
    return pool


def is_underwriter_offer_available(level_number):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    return level >= 3 and len(build_rare_silver_cards_pool()) >= 2


def build_shop_special_offer_pool(level_number=1):
    rolled = []
    delisting_hit = random.randint(1, 100) <= 80
    investment_hit = random.randint(1, 100) <= 35
    trader_hit = random.randint(1, 100) <= 80
    underwriter_hit = is_underwriter_offer_available(level_number) and random.randint(1, 100) <= 15
    bailout_hit = (not is_bailout_active()) and random.randint(1, 100) <= 50
    long_hit = is_long_offer_available() and random.randint(1, 100) <= 50
    junk_bond_hit = random.randint(1, 100) <= 40
    issuer_hit = is_issuer_offer_available() and random.randint(1, 100) <= 25
    bank_hit = is_bank_offer_available() and random.randint(1, 100) <= 50
    derivative_hit = is_derivative_offer_available() and random.randint(1, 100) <= 45

    if underwriter_hit:
        rolled.append("underwriter")
    if bailout_hit:
        rolled.append("bailout")
    if bank_hit:
        rolled.append("bank")
    if long_hit:
        rolled.append("long")
    if junk_bond_hit:
        rolled.append("junk_bond")
    if issuer_hit:
        rolled.append("issuer")
    if derivative_hit:
        rolled.append("derivative")
    if trader_hit:
        rolled.append("trader")
    if random.randint(1, 100) <= 20:
        rolled.append("profit")
    if delisting_hit:
        rolled.append("delisting")
    if investment_hit:
        rolled.append("investment")

    offers = rolled[:2]
    for offer_id in ("delisting", "investment", "trader", "profit"):
        if len(offers) >= 2:
            break
        if offer_id not in offers:
            offers.append(offer_id)
    return offers


def generate_shop_offers(level_number=1, card_slots=None, special_slots=2, license_slots=1, discount_percent=0):
    try:
        level = int(level_number or 0)
    except (TypeError, ValueError):
        level = 0
    if card_slots is None:
        card_slots = 1 if level >= 4 else 0

    bought_cards = get_bought_shop_card_ids()
    card_pool = list(build_shop_card_offer_pool(level))
    open_card_pool = [17, 18, 117]
    if level >= 4:
        for card_id in open_card_pool:
            if len(card_pool) >= card_slots:
                break
            if card_id not in bought_cards and card_id not in card_pool:
                card_pool.append(card_id)

    card_offers = []
    for card_id in card_pool[:card_slots]:
        normalized = int(card_id)
        card_offers.append({"kind": "card", "card_id": normalized, "cost": SHOP_CARD_COSTS.get(normalized, 1)})

    special_pool = build_shop_special_offer_pool(level)
    special_offers = [
        {"kind": "special", "special_id": offer_id, "cost": get_shop_special_cost(offer_id)}
        for offer_id in special_pool[:special_slots]
    ]
    license_pool = build_license_offer_pool(level)
    if license_slots is None:
        license_slots = len(license_pool)
    license_offers = [
        {"kind": "license", "card_id": int(card_id), "cost": get_license_cost(card_id)}
        for card_id in license_pool[:license_slots]
    ]
    offers = card_offers + special_offers + license_offers
    try:
        discount = max(0, min(100, int(discount_percent or 0)))
    except (TypeError, ValueError):
        discount = 0
    if discount:
        multiplier = (100 - discount) / 100
        for offer in offers:
            offer["cost"] = float(offer.get("cost", 0) or 0) * multiplier
    return offers


def start_red_cards_deck_for_level(level_num):
    """Build and store a fresh no-repeat red-card deck for the current boss attempt."""
    global active_red_cards_level, active_red_cards_deck
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0
    active_red_cards_level = level
    unavailable = get_unavailable_red_cards(level)
    active_red_cards_deck = [
        card_id for card_id in build_red_cards_deck_for_level(level) if int(card_id) not in unavailable
    ]
    random.shuffle(active_red_cards_deck)
    return list(active_red_cards_deck)


def draw_red_card_for_level(level_num):
    """Draw one red card without replacement for the current boss attempt."""
    global active_red_cards_level, active_red_cards_deck
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0

    if not level:
        return None
    if active_red_cards_level != level:
        start_red_cards_deck_for_level(level)
    else:
        remove_unavailable_red_cards_from_active_deck(level)
    if not active_red_cards_deck:
        return None
    return active_red_cards_deck.pop(0)


def pick_random_red_card_for_level(level_num):
    """Return and consume a random available red card for the level."""
    return draw_red_card_for_level(level_num)


def pick_random_gain_drop_card(excluded_card_ids=None):
    """Return a random currently available Gain/Drop card."""
    pool = build_gain_drop_cards_pool(excluded_card_ids=excluded_card_ids)
    if not pool:
        return None
    return random.choice(pool)


def pick_random_silver_card():
    """Return a random open silver card using Cards.csv Variable as inclusion chance."""
    pool = build_silver_cards_pool()
    if not pool:
        return None
    return random.choice(pool)


def pick_random_gold_card():
    """Return a random open gold card using Cards.csv Variable as inclusion chance."""
    pool = build_gold_cards_pool()
    if not pool:
        return None
    return random.choice(pool)


def start_silver_cards_deck_for_level(level_num):
    """Build and store the available silver-card pool for the current attempt."""
    global active_silver_cards_level, active_silver_cards_deck
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0
    active_silver_cards_level = level
    active_silver_cards_deck = build_silver_cards_pool()
    random.shuffle(active_silver_cards_deck)
    return list(active_silver_cards_deck)


def ensure_silver_cards_deck_for_level(level_num):
    """Keep the per-attempt silver pool compatible with current Cards.csv data."""
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0

    if active_silver_cards_level != level or not active_silver_cards_deck:
        return start_silver_cards_deck_for_level(level)

    open_cards = set(build_open_silver_cards_pool())
    required_cards = set(build_guaranteed_silver_cards_pool())
    current_cards = set()
    for card_id in active_silver_cards_deck or []:
        try:
            current_cards.add(int(card_id))
        except (TypeError, ValueError):
            continue

    if not current_cards.issubset(open_cards) or not required_cards.issubset(current_cards):
        return start_silver_cards_deck_for_level(level)
    return list(active_silver_cards_deck)


def draw_silver_card_for_level(level_num):
    """Pick one silver card from the current attempt's available pool."""
    global active_silver_cards_level, active_silver_cards_deck
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0
    ensure_silver_cards_deck_for_level(level)
    if not active_silver_cards_deck:
        return None
    return random.choice(active_silver_cards_deck)


def build_open_silver_cards_pool():
    """Return all open silver cards, without applying per-attempt probability."""
    cfg = load_cards_config() or {}
    silver_pool = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid <= 200 or cid >= 300:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if is_open:
            silver_pool.append(cid)
    silver_pool = [cid for cid in silver_pool if is_card_licensed(cid)]

    return sorted(set(silver_pool))


def build_rare_silver_cards_pool():
    """Return every open silver card whose pool probability is below 40%."""
    cfg = load_cards_config() or {}
    rare_cards = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid <= 200 or cid >= 300:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        probability_raw = row.get("Variable") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
            probability = int(probability_raw)
        except (TypeError, ValueError):
            continue
        if is_open and is_card_licensed(cid) and 0 < probability < 40:
            rare_cards.append(cid)

    return sorted(set(rare_cards))


def buy_underwriter_cards(count=2):
    """Add distinct random rare silver cards without using the current attempt pool."""
    try:
        card_count = int(count)
    except (TypeError, ValueError):
        return []
    if card_count <= 0 or len(silver_cards) + card_count > MAX_SILVER_CARDS:
        return []

    rare_cards = build_rare_silver_cards_pool()
    if len(rare_cards) < card_count:
        return []

    selected_cards = random.sample(rare_cards, card_count)
    silver_cards.extend(selected_cards)
    print(f"Underwriter awarded rare silver cards: {selected_cards}")
    return selected_cards


def build_guaranteed_silver_cards_pool():
    """Return open silver cards that must always be present in the per-attempt pool."""
    cfg = load_cards_config() or {}
    silver_pool = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid <= 200 or cid >= 300:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if not is_open:
            continue
        if not is_card_licensed(cid):
            continue

        probability_raw = row.get("Variable") if isinstance(row, dict) else None
        try:
            probability = int(probability_raw) if probability_raw is not None else 100
        except (TypeError, ValueError):
            probability = 100
        if probability >= 100:
            silver_pool.append(cid)

    return sorted(set(silver_pool))


def build_silver_cards_pool():
    """Build the open silver-card pool using Variable as inclusion chance."""
    cfg = load_cards_config() or {}
    silver_pool = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid <= 200 or cid >= 300:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if not is_open:
            continue
        if not is_card_licensed(cid):
            continue

        probability_raw = row.get("Variable") if isinstance(row, dict) else None
        try:
            probability = int(probability_raw) if probability_raw is not None else 100
        except (TypeError, ValueError):
            probability = 100
        probability = max(0, min(100, probability))

        if probability >= 100:
            silver_pool.append(cid)
        elif probability <= 0:
            continue
        else:
            roll = random.randint(1, 100)
            if roll <= probability:
                silver_pool.append(cid)

    return sorted(set(silver_pool))


def build_open_gold_cards_pool():
    """Return all open gold cards, without applying probability."""
    cfg = load_cards_config() or {}
    gold_pool = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if not is_gold_card(cid):
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if is_open:
            gold_pool.append(cid)

    return sorted(set(gold_pool))


def build_gold_cards_pool():
    """Build the open gold-card pool using Variable as inclusion chance."""
    cfg = load_cards_config() or {}
    gold_pool = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if not is_gold_card(cid):
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if not is_open:
            continue

        probability_raw = row.get("Variable") if isinstance(row, dict) else None
        try:
            probability = int(probability_raw) if probability_raw is not None else 100
        except (TypeError, ValueError):
            probability = 100
        probability = max(0, min(100, probability))

        if probability >= 100:
            gold_pool.append(cid)
        elif probability <= 0:
            continue
        else:
            roll = random.randint(1, 100)
            if roll <= probability:
                gold_pool.append(cid)

    return sorted(set(gold_pool))


def build_gain_drop_cards_pool(excluded_card_ids=None):
    """Build the pool of open Gain/Drop cards."""
    cfg = load_cards_config() or {}
    excluded = set()
    for card_id in excluded_card_ids or []:
        try:
            excluded.add(int(card_id))
        except (TypeError, ValueError):
            continue

    gain_drop_cards = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid < 11 or cid > 18:
            continue
        if cid in excluded:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if is_open:
            gain_drop_cards.append(cid)

    return sorted(set(gain_drop_cards))


def build_red_cards_deck_for_level(level_num):
    """Build the per-run deck of available red cards when a level is selected."""
    cfg = load_cards_config() or {}
    red_cards = []
    for card_id, row in cfg.items():
        try:
            cid = int(card_id)
        except (TypeError, ValueError):
            continue
        if cid <= 100 or cid >= 200:
            continue

        open_val = row.get("Open") if isinstance(row, dict) else None
        try:
            is_open = int(open_val) == 1
        except (TypeError, ValueError):
            is_open = False
        if not is_open:
            continue
        if not is_card_licensed(cid):
            continue

        prob_raw = row.get("Variable") if isinstance(row, dict) else None
        try:
            probability = int(prob_raw) if prob_raw is not None else 100
        except (TypeError, ValueError):
            probability = 100
        probability = max(0, min(100, probability))

        if probability >= 100:
            red_cards.append(cid)
        elif probability <= 0:
            continue
        else:
            roll = random.randint(1, 100)
            if roll <= probability:
                red_cards.append(cid)

    return sorted(set(red_cards))
