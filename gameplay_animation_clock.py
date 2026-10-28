"""Explicit pause policy for the existing pygame timestamp animations."""

# These are presentation clocks, not saved game state. Keep this list alongside
# new animations so modal/focus suspension never silently consumes their time.
SCALAR_CLOCKS = (
    'card_processing_start_time', 'hand_compact_start_time', 'hand_draw_start_time',
    'level6_bot_turn_started_at', 'finance_stamp_started_at', '_winlose_last_tick',
    'end_button_press_until', 'hedger_message_until', 'boss_turn_timer_last_tick',
)
ANIMATION_CLOCKS = (
    'card_jump_animations', 'side_card_jump_animations', 'lifecycle_card_jump_animations',
    'lifecycle_card_scale_animations', 'lifecycle_card_shake_animations',
    'market_clear_animations', 'current_price_animation', 'arrow_entries',
    'final_auto_liquidation_animation', 'astor_cash_burn_animation',
    'arkwright_share_theft_animation', 'bankruptcy_animations',
)


def shift_animation_clocks(page, elapsed):
    if elapsed <= 0:
        return
    for name in SCALAR_CLOCKS:
        value = getattr(page, name, None)
        if isinstance(value, (int, float)):
            setattr(page, name, value + elapsed)
    def shift(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('start_time', 'start', 'last_update', 'last') and isinstance(child, (int, float)):
                    value[key] = child + elapsed
                elif isinstance(child, (dict, list)):
                    shift(child)
        elif isinstance(value, list):
            for child in value:
                shift(child)
    for name in ANIMATION_CLOCKS:
        shift(getattr(page, name, None))


def sync_animation_clock(page, now, focused=True):
    """Freeze modals / lost focus; cap active catch-up after a stall to 250 ms."""
    paused = bool(page.deck_view_active or page.pause_menu_active
                  or getattr(page, 'tutorial_hint', None) is not None or not focused)
    previous = getattr(page, '_animation_clock_tick', now)
    delta = max(0, now - previous)
    suspended = getattr(page, '_animation_clock_paused', paused)
    shift_animation_clocks(page, delta if suspended else max(0, delta - 250))
    page._animation_clock_tick = now
    page._animation_clock_paused = paused
    return paused
