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

# Napoleondors are earned and spent inside the current level run.
napoleondors = 0
napoleondor_level = None

# Reward cards earned by player: {level_number: [list of card_ids]}.
earned_reward_cards = {}

# Non-gold cards bought in shops. They persist through boss victories and are
# cleared only when the current run is lost.
shop_deck_cards = []

# Cards removed from the current level deck by shop offers.
removed_deck_cards_by_level = {}

# Permanent-until-defeat +1 bonuses for Gain/Drop cards bought through Investment.
investment_card_bonuses = {}
profit_reward_bonus = 0
pending_shop_discount_percent = 0

SHOP_SPECIAL_COSTS = {
    "delisting": 3,
    "investment": 5,
    "trader": 0,
    "profit": 15,
    "underwriter": 12,
}

SHOP_CARD_COSTS = {
    17: 10,
    18: 15,
    117: 7,
    401: 15,
    402: 10,
    403: 15,
}

# Active per-level "red cards" deck rebuilt on level selection.
active_red_cards_level = None
active_red_cards_deck = []

# Active per-level silver reward pool rebuilt lazily per attempt.
active_silver_cards_level = None
active_silver_cards_deck = []

# Forced "starting hand" cards by level, used by RedCard boss rewards.
forced_start_hand_cards_by_level = {}

# Permanent cards unlocked by completing levels.
LEVEL_COMPLETION_REWARD_CARDS = {
    1: [12],
    2: [13],
}

# Silver cards are kept outside the regular deck. They are spent after the
# round where they were selected.
MAX_CARD_SLOTS = 8
MAX_SILVER_CARDS = MAX_CARD_SLOTS
MAX_BLACK_CARDS = MAX_CARD_SLOTS
MAX_GOLD_CARDS = MAX_CARD_SLOTS
silver_cards = []

# Black cards are permanent profile unlocks. Gold cards last for the current
# run and are cleared only after a defeat. Active gold cards stay equipped
# between rounds until the run ends.
black_cards = []
gold_cards = []
active_gold_cards = []
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
    return _add_card_to_inventory(gold_cards, MAX_GOLD_CARDS, card_id, "Gold")


def add_shop_card_to_level(level_number, card_id):
    """Buy a card from the shop: gold cards go to inventory, regular cards persist for the run."""
    normalized = _normalize_card_id(card_id)
    if normalized is None:
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


def clear_shop_deck_cards():
    if shop_deck_cards:
        print(f"Cleared shop-bought cards after defeat: {shop_deck_cards}")
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


def clear_gold_cards():
    global bear_goal_reduction_steps
    if gold_cards:
        cleared = list(gold_cards)
        gold_cards.clear()
        print(f"Cleared gold cards after defeat: {cleared}")
    if active_gold_cards:
        active_gold_cards.clear()
        print("Cleared active gold cards after defeat.")
    bear_goal_reduction_steps = 0


def set_active_gold_cards(selected_cards):
    """Persist equipped gold cards, preserving duplicate-card inventory counts."""
    active_gold_cards.clear()
    available = list(gold_cards or [])
    for card_id in selected_cards or []:
        normalized = _normalize_card_id(card_id)
        if normalized is None:
            continue
        try:
            available.remove(normalized)
        except ValueError:
            continue
        active_gold_cards.append(normalized)
    return list(active_gold_cards)


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
        napoleondors = 0
    return napoleondors


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
    napoleondors = 0
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
    for card_id in earned_reward_cards.get(level, []) or []:
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
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus
    global profit_reward_bonus
    global_dobor = 1
    global_start_money_bonus = 0
    global_last_turn_bonus = 0
    global_hand_bonus = 0
    profit_reward_bonus = 0
    reset_napoleondors(level_number)
    clear_removed_deck_cards(level_number)
    clear_investment_card_bonuses()
    clear_pending_shop_discount()
    clear_shop_deck_cards()
    clear_gold_cards()
    clear_silver_cards_deck()
    clear_insurance_goal_debt()
    state = new_boss_progress_state()
    boss_progress[int(level_number)] = state
    return state


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
        "napoleondors": float(napoleondors),
        "napoleondor_level": napoleondor_level,
        "earned_reward_cards": list(earned_reward_cards.get(level, []) or []),
        "removed_deck_cards": list(removed_deck_cards_by_level.get(level, []) or []),
        "forced_start_hand_cards": list(forced_start_hand_cards_by_level.get(level, []) or []),
    }
    return True


def restore_level2_loss_checkpoint(level_number):
    """Restore level-2 boss progress and first-boss rewards after a defeat."""
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus
    global napoleondors, napoleondor_level, profit_reward_bonus
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
    napoleondors = float(checkpoint.get("napoleondors", napoleondors) or 0)
    try:
        napoleondor_level = int(checkpoint.get("napoleondor_level", level))
    except (TypeError, ValueError):
        napoleondor_level = level
    earned_reward_cards[level] = list(checkpoint.get("earned_reward_cards") or [])
    removed_deck_cards_by_level[level] = list(checkpoint.get("removed_deck_cards") or [])
    forced_start_hand_cards_by_level[level] = list(checkpoint.get("forced_start_hand_cards") or [])

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
    )


def is_gain_drop_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 11 <= cid <= 18


def get_current_gain_drop_deck_cards(level_number):
    seen = set()
    result = []
    for card_id in build_current_level_deck(level_number):
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            continue
        if not is_gain_drop_card(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def invest_gain_drop_card(card_id):
    try:
        normalized = int(card_id)
    except (TypeError, ValueError):
        return False
    if not is_gain_drop_card(normalized):
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


def clear_profit_bonus():
    global profit_reward_bonus
    if profit_reward_bonus:
        print(f"Cleared Profit bonus: {profit_reward_bonus}")
    profit_reward_bonus = 0


def get_victory_napoleondor_reward(base_amount):
    try:
        base = float(base_amount or 0)
    except (TypeError, ValueError):
        base = 0.0
    return base + int(profit_reward_bonus or 0)


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
    current_deck = build_current_level_deck(level)
    if normalized not in current_deck:
        print(f"WARNING: Card {normalized} is not available in level {level} deck.")
        return False
    removed_deck_cards_by_level.setdefault(level, []).append(normalized)
    print(f"Delisted card {normalized} from level {level} deck.")
    return True


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

    available_deck = build_current_level_deck(level)
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


def build_shop_card_offer_pool():
    """Return shop-buyable card offers."""
    pool = []
    for card_id, chance in ((17, 5), (18, 5), (117, 50)):
        if random.randint(1, 100) <= chance:
            pool.append(card_id)

    for card_id in build_gold_cards_pool():
        if card_id not in pool:
            pool.append(card_id)
    return pool


def build_shop_special_offer_pool():
    rolled = []
    delisting_hit = random.randint(1, 100) <= 80
    investment_hit = random.randint(1, 100) <= 35
    trader_hit = random.randint(1, 100) <= 80
    underwriter_hit = random.randint(1, 100) <= 15

    if underwriter_hit:
        rolled.append("underwriter")
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


def generate_shop_offers(card_slots=2, special_slots=2, discount_percent=0):
    card_pool = list(build_shop_card_offer_pool())
    open_card_pool = [17, 18, 117]
    for card_id in open_card_pool:
        if len(card_pool) >= card_slots:
            break
        if card_id not in card_pool:
            card_pool.append(card_id)

    card_offers = []
    for card_id in card_pool[:card_slots]:
        normalized = int(card_id)
        card_offers.append({"kind": "card", "card_id": normalized, "cost": SHOP_CARD_COSTS.get(normalized, 1)})

    special_pool = build_shop_special_offer_pool()
    special_offers = [
        {"kind": "special", "special_id": offer_id, "cost": SHOP_SPECIAL_COSTS.get(offer_id, 1)}
        for offer_id in special_pool[:special_slots]
    ]
    offers = card_offers + special_offers
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
        if is_open and 0 < probability < 40:
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
