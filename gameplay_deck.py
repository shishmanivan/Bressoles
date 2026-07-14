import random

from game_data import REWARD_TOKEN_RANDOM_SILVER


BASE_STARTING_DECK = [100, 1, 1, 2, 3, 4, 11]


def normalize_card_id(card_id):
    """Map legacy card 0 references to card 100."""
    return 100 if card_id == 0 else card_id


def is_red_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return 100 < cid < 200


def dedupe_red_cards(cards):
    result = []
    seen_red_cards = set()
    for card_id in cards or []:
        normalized = normalize_card_id(card_id)
        if is_red_card(normalized):
            if normalized in seen_red_cards:
                continue
            seen_red_cards.add(normalized)
        result.append(normalized)
    return result


def is_silver_reward_card(card_id):
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return False
    return cid == REWARD_TOKEN_RANDOM_SILVER or 200 < cid < 300


def apply_removed_cards(deck, removed_cards):
    result = list(deck or [])
    for card_id in removed_cards or []:
        normalized = normalize_card_id(card_id)
        try:
            result.remove(normalized)
        except ValueError:
            pass
    return result


def build_initial_deck(
    level_number,
    earned_reward_cards,
    level_completion_reward_cards=None,
    removed_cards_by_level=None,
    shop_deck_cards=None,
    temporary_reward_cards=None,
):
    """Build initial deck composition for a given level."""
    base_deck = list(BASE_STARTING_DECK)

    completion_cards = dedupe_red_cards(level_completion_reward_cards or [])
    if completion_cards:
        base_deck.extend(completion_cards)
        print(f"Added {len(completion_cards)} completed-level reward card(s) to starting deck: {completion_cards}")

    earned_cards = dedupe_red_cards(
        card_id for card_id in earned_reward_cards.get(level_number, []) if not is_silver_reward_card(card_id)
    )
    if earned_cards:
        base_deck.extend(earned_cards)
        print(f"Added {len(earned_cards)} earned reward card(s) to level {level_number} deck: {earned_cards}")

    bought_cards = dedupe_red_cards(
        card_id for card_id in (shop_deck_cards or []) if not is_silver_reward_card(card_id)
    )
    if bought_cards:
        base_deck.extend(bought_cards)
        print(f"Added {len(bought_cards)} shop-bought card(s) to the run deck: {bought_cards}")

    temporary_cards = dedupe_red_cards(
        card_id for card_id in (temporary_reward_cards or []) if not is_silver_reward_card(card_id)
    )
    if temporary_cards:
        base_deck.extend(temporary_cards)
        print(f"Added {len(temporary_cards)} temporary reward card(s) to level {level_number} deck: {temporary_cards}")

    deck = dedupe_red_cards(base_deck)
    removed_cards = (removed_cards_by_level or {}).get(level_number, [])
    if removed_cards:
        deck = apply_removed_cards(deck, removed_cards)
        print(f"Removed {len(removed_cards)} card(s) from level {level_number} deck: {removed_cards}")

    return deck


def deal_starting_hand(deck, hand_size, guaranteed_cards):
    """Deal a starting hand and return the remaining deck plus fixed-slot hand."""
    deck = [normalize_card_id(card_id) for card_id in deck]
    random.shuffle(deck)

    try:
        hand_size = max(0, int(hand_size or 0))
    except (TypeError, ValueError):
        hand_size = 0

    guaranteed_cards = dedupe_red_cards(
        card_id for card_id in (guaranteed_cards or []) if card_id is not None
    )
    available_guaranteed_cards = []

    # Guaranteed cards that do not fit remain in the shuffled deck.
    for card_id in guaranteed_cards[:hand_size]:
        try:
            deck.remove(card_id)
            available_guaranteed_cards.append(card_id)
        except ValueError:
            pass

    hand_cards = [None] * hand_size
    for slot, card_id in enumerate(available_guaranteed_cards):
        hand_cards[slot] = card_id

    fill_idx = len(available_guaranteed_cards)
    draw_count = max(0, hand_size - fill_idx)
    drawn = deck[:draw_count] if draw_count > 0 else []
    for offset, card_id in enumerate(drawn):
        slot_idx = fill_idx + offset
        if slot_idx < hand_size:
            hand_cards[slot_idx] = normalize_card_id(card_id)

    remaining_deck = deck[draw_count:] if len(deck) > draw_count else []
    return remaining_deck, hand_cards


def setup_starting_deck_and_hand(
    level_number,
    hand_size,
    earned_reward_cards,
    level_completion_reward_cards=None,
    removed_cards_by_level=None,
    shop_deck_cards=None,
    temporary_reward_cards_by_level=None,
    guaranteed_cards_by_level=None,
):
    """Build, shuffle, and deal the starting deck/hand for GameplayPage."""
    deck = build_initial_deck(
        level_number,
        earned_reward_cards,
        level_completion_reward_cards,
        removed_cards_by_level,
        shop_deck_cards,
        (temporary_reward_cards_by_level or {}).get(level_number, []),
    )
    guaranteed_cards = list((guaranteed_cards_by_level or {}).get(level_number, []) or [])
    return deal_starting_hand(deck, hand_size, guaranteed_cards)
