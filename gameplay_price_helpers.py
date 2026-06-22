import random


BASE_MARKET_PROBABILITIES = {
    0: {"fall": 0.0, "flat": 15.0, "rise": 85.0},
    1: {"fall": 10.0, "flat": 20.0, "rise": 70.0},
    2: {"fall": 30.0, "flat": 20.0, "rise": 50.0},
}

UPSIDE_CARD_BONUSES = {
    1: 5.0,
    2: 10.0,
}

DOWNSIDE_CARD_BONUSES = {
    3: 5.0,
    4: 10.0,
}


def get_card_type_from_config(card_types, card_id):
    """Return card Type from Cards.csv config, defaulting to 1."""
    if card_id is None:
        return 1
    try:
        return int(card_types.get(card_id, 1))
    except Exception:
        return 1


def _take_probability(probs, donors, amount):
    remaining = float(amount)
    positive_donors = [donor for donor in donors if probs.get(donor, 0.0) > 0.0]
    if not positive_donors or remaining <= 0.0:
        return 0.0

    preferred_take = remaining / len(positive_donors)
    taken = 0.0
    for donor in positive_donors:
        take = min(preferred_take, probs.get(donor, 0.0))
        probs[donor] -= take
        taken += take
        remaining -= take

    while remaining > 0.0001:
        donor = max(donors, key=lambda key: probs.get(key, 0.0))
        available = probs.get(donor, 0.0)
        if available <= 0.0:
            break
        take = min(remaining, available)
        probs[donor] -= take
        taken += take
        remaining -= take

    return taken


def _apply_probability_shift(probs, target, donors, amount):
    taken = _take_probability(probs, donors, amount)
    probs[target] += taken


def build_market_probabilities(market_cards=None):
    """Return per-market probabilities after applying Upside/Downside cards."""
    probabilities = {
        market: dict(values)
        for market, values in BASE_MARKET_PROBABILITIES.items()
    }

    for market, slots in (market_cards or {}).items():
        if market not in probabilities:
            continue
        probs = probabilities[market]
        for slot in sorted((slots or {}).keys()):
            card_id = slots.get(slot)
            if card_id in UPSIDE_CARD_BONUSES:
                _apply_probability_shift(
                    probs,
                    "rise",
                    ("flat", "fall"),
                    UPSIDE_CARD_BONUSES[card_id],
                )
            elif card_id in DOWNSIDE_CARD_BONUSES:
                _apply_probability_shift(
                    probs,
                    "fall",
                    ("flat", "rise"),
                    DOWNSIDE_CARD_BONUSES[card_id],
                )

    return probabilities


def build_stock_price_animation_queue(step_a, step_b, step_c, market_cards=None):
    """Build price animation queue from the stock probability rules."""
    animation_queue = []
    probabilities = build_market_probabilities(market_cards)

    rand_a = random.random() * 100
    probs_a = probabilities[0]
    if rand_a <= probs_a["fall"]:
        animation_queue.append({"market": 0, "type": "fall", "price_change": -step_a})
    elif rand_a <= probs_a["fall"] + probs_a["flat"]:
        animation_queue.append({"market": 0, "type": "unchanged", "price_change": 0})
    else:
        animation_queue.append({"market": 0, "type": "rise", "price_change": step_a})

    rand_b = random.random() * 100
    probs_b = probabilities[1]
    if rand_b <= probs_b["fall"]:
        animation_queue.append({"market": 1, "type": "fall", "price_change": -step_b})
    elif rand_b <= probs_b["fall"] + probs_b["flat"]:
        animation_queue.append({"market": 1, "type": "unchanged", "price_change": 0})
    else:
        animation_queue.append({"market": 1, "type": "rise", "price_change": step_b})

    rand_c = random.random() * 100
    probs_c = probabilities[2]
    if rand_c <= probs_c["fall"]:
        animation_queue.append({"market": 2, "type": "fall", "price_change": -step_c})
    elif rand_c <= probs_c["fall"] + probs_c["flat"]:
        animation_queue.append({"market": 2, "type": "unchanged", "price_change": 0})
    else:
        animation_queue.append({"market": 2, "type": "rise", "price_change": step_c})

    return animation_queue


def apply_market_price_change(prices, market, price_change, minimum_price=2):
    """Return updated prices after applying a market price change."""
    updated = dict(prices)
    if market == 0:
        updated["Aprice"] = max(minimum_price, updated["Aprice"] + price_change)
    elif market == 1:
        updated["BPrice"] = max(minimum_price, updated["BPrice"] + price_change)
    elif market == 2:
        updated["CPrice"] = max(minimum_price, updated["CPrice"] + price_change)
    return updated


def update_arrow_animation_entries(arrow_entries, arrow_anim_sequence, arrow_anim_interval, now):
    """Advance active arrow animation entries in place."""
    if not arrow_entries:
        return
    for entry in arrow_entries:
        if not entry["animating"]:
            continue
        if now - entry["last"] >= arrow_anim_interval:
            entry["last"] = now
            entry["idx"] += 1
            if entry["idx"] >= len(arrow_anim_sequence):
                entry["animating"] = False
                entry["idx"] = 0


def compute_slide_position(current_y, target_y, speed_pps, dt, move_towards):
    """Compute a dt-based slide animation position."""
    max_delta = float(speed_pps) * dt
    return move_towards(float(current_y), float(target_y), max_delta)
