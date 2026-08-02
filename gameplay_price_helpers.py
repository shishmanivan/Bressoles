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

GAMBLING_PROBABILITY_BONUS = 7.0


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


def build_market_probabilities(
    market_cards=None,
    probability_card_bonus=0,
    force_flat=False,
    force_flat_markets=None,
    double_fall_markets=None,
    double_fall_bonus=0,
):
    """Return per-market probabilities after applying Upside/Downside cards."""
    if force_flat:
        return {
            market: {"fall": 0.0, "flat": 100.0, "rise": 0.0}
            for market in BASE_MARKET_PROBABILITIES
        }

    probabilities = {
        market: dict(values)
        for market, values in BASE_MARKET_PROBABILITIES.items()
    }
    forced_flat = _normalize_market_set(force_flat_markets)
    doubled_fall = _normalize_market_set(double_fall_markets)
    try:
        probability_card_bonus = max(0.0, float(probability_card_bonus or 0))
    except (TypeError, ValueError):
        probability_card_bonus = 0.0
    try:
        double_fall_bonus = max(0.0, float(double_fall_bonus or 0))
    except (TypeError, ValueError):
        double_fall_bonus = 0.0

    for market, slots in (market_cards or {}).items():
        if market not in probabilities:
            continue
        if market in forced_flat:
            probabilities[market] = {"fall": 0.0, "flat": 100.0, "rise": 0.0}
            continue
        probs = probabilities[market]
        for slot in sorted((slots or {}).keys()):
            card_id = slots.get(slot)
            if card_id in UPSIDE_CARD_BONUSES:
                _apply_probability_shift(
                    probs,
                    "rise",
                    ("flat", "fall"),
                    UPSIDE_CARD_BONUSES[card_id] + probability_card_bonus,
                )
            elif card_id in DOWNSIDE_CARD_BONUSES:
                _apply_probability_shift(
                    probs,
                    "fall",
                    ("flat", "rise"),
                    DOWNSIDE_CARD_BONUSES[card_id] + probability_card_bonus,
                )

    for market in doubled_fall:
        if market not in probabilities or market in forced_flat:
            continue
        probs = probabilities[market]
        _apply_probability_shift(
            probs,
            "fall",
            ("flat", "rise"),
            probs["fall"] + double_fall_bonus,
        )

    return probabilities


def _normalize_market_set(markets):
    forced = set()
    for market in markets or []:
        try:
            forced.add(int(market))
        except (TypeError, ValueError):
            continue
    return forced


def _roll_market_animation(market, step, probabilities, forced_rise_markets):
    if market in forced_rise_markets:
        return {"market": market, "type": "rise", "price_change": step}

    rand_value = random.random() * 100
    probs = probabilities[market]
    if rand_value <= probs["fall"]:
        return {"market": market, "type": "fall", "price_change": -step}
    if rand_value <= probs["fall"] + probs["flat"]:
        return {"market": market, "type": "unchanged", "price_change": 0}
    return {"market": market, "type": "rise", "price_change": step}


def build_stock_price_animation_queue(
    step_a,
    step_b,
    step_c,
    market_cards=None,
    forced_rise_markets=None,
    probability_card_bonus=0,
    force_flat=False,
    force_flat_markets=None,
    double_fall_markets=None,
    double_fall_bonus=0,
):
    """Build price animation queue from the stock probability rules."""
    forced_rise_markets = _normalize_market_set(forced_rise_markets)
    if force_flat:
        steps = {0: step_a, 1: step_b, 2: step_c}
        return [
            (
                {"market": market, "type": "rise", "price_change": steps[market]}
                if market in forced_rise_markets
                else {"market": market, "type": "unchanged", "price_change": 0}
            )
            for market in (0, 1, 2)
        ]

    probabilities = build_market_probabilities(
        market_cards,
        probability_card_bonus=probability_card_bonus,
        force_flat_markets=force_flat_markets,
        double_fall_markets=double_fall_markets,
        double_fall_bonus=double_fall_bonus,
    )

    return [
        _roll_market_animation(0, step_a, probabilities, forced_rise_markets),
        _roll_market_animation(1, step_b, probabilities, forced_rise_markets),
        _roll_market_animation(2, step_c, probabilities, forced_rise_markets),
    ]


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
