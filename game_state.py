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
# run and are cleared only after a defeat.
black_cards = []
gold_cards = []


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
    if gold_cards:
        cleared = list(gold_cards)
        gold_cards.clear()
        print(f"Cleared gold cards after defeat: {cleared}")


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
        earned = int(amount or 0)
    except (TypeError, ValueError):
        earned = 0
    if earned <= 0:
        return napoleondors
    napoleondors += earned
    print(f"Earned {earned} napoleondor(s) on level {level_number}: balance={napoleondors}")
    return napoleondors


def spend_napoleondors(amount):
    global napoleondors
    try:
        cost = int(amount or 0)
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
    global_dobor = 1
    global_start_money_bonus = 0
    global_last_turn_bonus = 0
    global_hand_bonus = 0
    reset_napoleondors(level_number)
    clear_gold_cards()
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
        "napoleondors": int(napoleondors),
        "napoleondor_level": napoleondor_level,
        "earned_reward_cards": list(earned_reward_cards.get(level, []) or []),
        "forced_start_hand_cards": list(forced_start_hand_cards_by_level.get(level, []) or []),
    }
    return True


def restore_level2_loss_checkpoint(level_number):
    """Restore level-2 boss progress and first-boss rewards after a defeat."""
    global global_dobor, global_start_money_bonus, global_last_turn_bonus, global_hand_bonus
    global napoleondors, napoleondor_level
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
    napoleondors = int(checkpoint.get("napoleondors", napoleondors) or 0)
    try:
        napoleondor_level = int(checkpoint.get("napoleondor_level", level))
    except (TypeError, ValueError):
        napoleondor_level = level
    earned_reward_cards[level] = list(checkpoint.get("earned_reward_cards") or [])
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


def draw_silver_card_for_level(level_num):
    """Pick one silver card from the current attempt's available pool."""
    global active_silver_cards_level, active_silver_cards_deck
    try:
        level = int(level_num or 0)
    except (TypeError, ValueError):
        level = 0
    if active_silver_cards_level != level or not active_silver_cards_deck:
        start_silver_cards_deck_for_level(level)
    if not active_silver_cards_deck:
        return None
    return random.choice(active_silver_cards_deck)


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
