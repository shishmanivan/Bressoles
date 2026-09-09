from card_catalog import MARKET_DURATION_CARD_IDS, PRICE_CARD_IDS, get_price_card_spec
from gameplay_price_helpers import protect_market_prices


def lock_market_cards(market_cards, market_cards_locked):
    """Mark currently played market cards as locked."""
    for market in (0, 1, 2):
        for slot, card_id in list(market_cards[market].items()):
            if card_id is not None:
                market_cards_locked[market][slot] = True


def lock_side_cards(side_cards_top, side_cards_locked_top):
    """Mark currently played side-panel cards as locked."""
    for slot, card_id in enumerate(side_cards_top):
        if card_id is not None:
            side_cards_locked_top[slot] = True


def start_next_price_animation(price_animation_queue, now):
    """Pop the next price animation and build current animation state."""
    if not price_animation_queue:
        return None, None
    next_anim = price_animation_queue.pop(0)
    current_animation = {
        "market": next_anim["market"],
        "type": next_anim["type"],
        "frame_idx": 0,
        "last_update": now,
    }
    return next_anim, current_animation


def get_price_animation_frames(current_price_animation, unchanged_frames, rise_frames, fall_frames):
    """Return the frame list for the active price animation type."""
    if not current_price_animation:
        return []
    animation_type = current_price_animation.get("type", "unchanged")
    if animation_type == "unchanged":
        return unchanged_frames
    if animation_type == "rise":
        return rise_frames
    if animation_type == "fall":
        return fall_frames
    return []


def advance_price_animation_frame(current_price_animation, frame_count, interval_ms, now):
    """Advance current price animation frame if due. Return True when completed."""
    if not current_price_animation:
        return False
    if now - current_price_animation["last_update"] < interval_ms:
        return False

    current_price_animation["last_update"] = now
    current_price_animation["frame_idx"] += 1
    return current_price_animation["frame_idx"] >= frame_count


def build_price_cards_processing_queue(market_cards, market_card_turns):
    """Build the persistent market-effect queue in market/slot order."""
    queue = []
    for market in (0, 1, 2):
        for slot in (0, 1, 2):
            card_id = market_cards[market].get(slot)
            if card_id not in MARKET_DURATION_CARD_IDS:
                continue
            turns_remaining = market_card_turns[market].get(slot)
            if turns_remaining is not None and turns_remaining > 0:
                queue.append((market, slot))
    return queue


def apply_price_card_action(prices, market, card_id, card_action, minimum_price=2):
    """Apply a card 11-18 price effect and return updated prices."""
    updated = dict(prices)
    if card_action == 0:
        return updated

    price_keys = {0: "Aprice", 1: "BPrice", 2: "CPrice"}
    price_key = price_keys.get(market)
    if price_key is None:
        return updated

    card_spec = get_price_card_spec(card_id)
    if card_spec and card_spec.operation == "multiply":
        updated[price_key] = max(minimum_price, int(updated[price_key] * card_action))
    else:
        updated[price_key] = max(minimum_price, updated[price_key] + card_action)
    return updated


def calculate_price_card_prices(previous_prices, market, card_id, card_action, protected_markets=()):
    """Return A/B/C prices for a Gain/Drop effect, including Blue Chips protection.

    card_action is the effective value after per-card modifiers. Regulation affects
    the random market roll, so it does not suppress this explicit card effect.
    Inputs are not mutated; reactions, durations and animations belong to the caller.
    """
    prices = apply_price_card_action(
        dict(zip(("Aprice", "BPrice", "CPrice"), previous_prices)),
        market,
        card_id,
        card_action,
    )
    return protect_market_prices(
        previous_prices,
        (prices["Aprice"], prices["BPrice"], prices["CPrice"]),
        protected_markets,
    )
