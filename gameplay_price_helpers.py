import random


def get_card_type_from_config(card_types, card_id):
    """Return card Type from Cards.csv config, defaulting to 1."""
    if card_id is None:
        return 1
    try:
        return int(card_types.get(card_id, 1))
    except Exception:
        return 1


def build_stock_price_animation_queue(step_a, step_b, step_c):
    """Build price animation queue from the stock probability rules."""
    animation_queue = []

    rand_a = random.random() * 100
    if rand_a <= 15:
        animation_queue.append({"market": 0, "type": "unchanged", "price_change": 0})
    else:
        animation_queue.append({"market": 0, "type": "rise", "price_change": step_a})

    rand_b = random.random() * 100
    if rand_b <= 10:
        animation_queue.append({"market": 1, "type": "fall", "price_change": -step_b})
    elif rand_b <= 30:
        animation_queue.append({"market": 1, "type": "unchanged", "price_change": 0})
    else:
        animation_queue.append({"market": 1, "type": "rise", "price_change": step_b})

    rand_c = random.random() * 100
    if rand_c <= 30:
        animation_queue.append({"market": 2, "type": "fall", "price_change": -step_c})
    elif rand_c <= 50:
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
