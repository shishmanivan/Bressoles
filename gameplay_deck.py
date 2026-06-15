import random


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


def build_initial_deck(level_number, earned_reward_cards):
    """Build initial deck composition for a given level."""
    if level_number == 1:
        base_deck = [100, 1, 1, 2, 3, 4, 11]
    elif level_number == 2:
        base_deck = [100, 1, 1, 2, 3, 4, 11, 12]
    else:
        base_deck = [100, 100, 1, 1, 2, 3, 3, 4, 11, 12, 13, 14, 15, 16, 17, 18]

    earned_cards = dedupe_red_cards(earned_reward_cards.get(level_number, []))
    if earned_cards:
        base_deck.extend(earned_cards)
        print(f"Added {len(earned_cards)} earned reward card(s) to level {level_number} deck: {earned_cards}")

    return dedupe_red_cards(base_deck)


def deal_starting_hand(deck, hand_size, forced_cards):
    """Deal a starting hand and return the remaining deck plus fixed-slot hand."""
    deck = [normalize_card_id(card_id) for card_id in deck]
    random.shuffle(deck)

    forced_cards = dedupe_red_cards(card_id for card_id in forced_cards if card_id is not None)

    # Preserve legacy behavior: remove every forced card from the deck before
    # truncating forced cards to the available hand size.
    for card_id in forced_cards:
        try:
            deck.remove(card_id)
        except ValueError:
            pass

    hand_cards = [None] * hand_size
    forced_cards = forced_cards[:hand_size]
    for slot, card_id in enumerate(forced_cards):
        hand_cards[slot] = card_id

    fill_idx = len(forced_cards)
    draw_count = max(0, hand_size - fill_idx)
    drawn = deck[:draw_count] if draw_count > 0 else []
    for offset, card_id in enumerate(drawn):
        slot_idx = fill_idx + offset
        if slot_idx < hand_size:
            hand_cards[slot_idx] = normalize_card_id(card_id)

    remaining_deck = deck[draw_count:] if len(deck) > draw_count else []
    return remaining_deck, hand_cards


def setup_starting_deck_and_hand(level_number, hand_size, earned_reward_cards, forced_cards_by_level):
    """Build, shuffle, and deal the starting deck/hand for GameplayPage."""
    deck = build_initial_deck(level_number, earned_reward_cards)
    forced_cards = list(forced_cards_by_level.get(level_number, []) or [])
    return deal_starting_hand(deck, hand_size, forced_cards)
