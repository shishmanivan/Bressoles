"""Run-wide Bankruptcy condition; independent of campaign level numbers."""

import random
import game_state
import gameplay_condition_coins as condition_coins

import gameplay_bankruptcy_animation as animation
from gameplay_conditions import BANKRUPTCY, has_active_condition


def serialize(page):
    return {
        "chance": getattr(page, "bankruptcy_condition_chance", 0),
        "last_roll_day": getattr(page, "bankruptcy_condition_last_roll_day", None),
        "cards_counted": bool(getattr(page, "bankruptcy_condition_cards_counted", False)),
    }


def restore(page, state):
    try:
        chance = int(state.get("chance", 0) or 0)
    except (TypeError, ValueError):
        chance = 0
    # Legacy active-game snapshots may contain the only saved accumulated chance.
    page.bankruptcy_condition_chance = game_state.set_bankruptcy_condition_chance(
        max(game_state.bankruptcy_condition_chance, chance)
    )
    page.bankruptcy_condition_last_roll_day = state.get("last_roll_day")
    page.bankruptcy_condition_cards_counted = bool(state.get("cards_counted", False))


def register_fresh_cards(page):
    """Count committed cards once, even when red-card animations resume."""
    if not has_active_condition(page, BANKRUPTCY):
        return
    if getattr(page, "bankruptcy_condition_cards_counted", False):
        return
    page.bankruptcy_condition_cards_counted = True
    chance = getattr(page, "bankruptcy_condition_chance", 0)
    locked = getattr(page, "side_cards_locked_top", {})
    for slot, card in enumerate(getattr(page, "side_cards_top", ())):
        if locked.get(slot):
            continue
        try:
            card = int(card)
        except (TypeError, ValueError):
            continue
        if card not in (113, 114, 115, 117):
            continue
        chance = 5 if chance == 0 else min(100, chance + (2 if card == 117 else 1))
    page.bankruptcy_condition_chance = game_state.set_bankruptcy_condition_chance(chance)


def resolve_turn(page):
    """Roll once after card effects; use the normal Bankruptcy price/animation path."""
    if not has_active_condition(page, BANKRUPTCY):
        return False
    if not getattr(page, "turn_resolution_active", False) or getattr(page, "win_lose_state", None) is not None:
        return False
    if getattr(page, "bankruptcy_condition_last_roll_day", None) == page.Day:
        return False
    page.bankruptcy_condition_last_roll_day = page.Day
    chance = getattr(page, "bankruptcy_condition_chance", 0)
    if chance <= 0 or random.random() >= chance / 100:
        return False
    market = random.choice((0, 1, 2))
    changed = page._set_market_price_to_minimum(market)
    if not changed or getattr(page, "win_lose_state", None) is not None:
        return False
    condition_coins.show(page, BANKRUPTCY, market)
    animation.start(page, market)
    return True
