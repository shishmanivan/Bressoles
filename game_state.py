import random

from game_data import load_cards_config


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

# Reward cards earned by player: {level_number: [list of card_ids]}.
earned_reward_cards = {}

# Active per-level "red cards" deck rebuilt on level selection.
active_red_cards_level = None
active_red_cards_deck = []

# Forced "starting hand" cards by level, used by RedCard boss rewards.
forced_start_hand_cards_by_level = {}


def is_red_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 100 < cid < 200


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
    }


def reset_level_attempt(level_number):
    global global_dobor, global_start_money_bonus
    global_dobor = 1
    global_start_money_bonus = 0
    state = new_boss_progress_state()
    boss_progress[int(level_number)] = state
    return state


def get_progress_flags():
    """Return unlock flags for the level selection screen."""
    return {
        "level_1_boss_defeated": level_1_boss_defeated,
        "level_2_boss_defeated": level_2_boss_defeated,
        "level_3_boss_defeated": level_3_boss_defeated,
    }


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
