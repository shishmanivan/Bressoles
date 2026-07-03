import pygame


def find_hand_drag_start(mouse_pos, hand_layout, hand_cards, card_size_bottom):
    """Return drag state for a hand card click, or None."""
    if not hand_layout:
        return None

    for index in reversed(range(len(hand_layout["slot_positions"]))):
        slot_x, slot_y = hand_layout["slot_positions"][index]
        if index >= len(hand_cards) or hand_cards[index] is None:
            continue
        card_rect = pygame.Rect(slot_x - 2, slot_y - 2, card_size_bottom[0], card_size_bottom[1])
        if card_rect.collidepoint(mouse_pos):
            return {
                "dragged_card_index": index,
                "dragged_card_source": "hand",
                "drag_offset": (mouse_pos[0] - slot_x, mouse_pos[1] - slot_y),
                "dragged_card_pos": mouse_pos,
            }
    return None


def find_market_drag_start(mouse_pos, market_placeholders, market_cards, market_cards_locked):
    """Return drag state for the last unlocked market card, or None."""
    for ph_info in market_placeholders:
        market = ph_info["market"]
        slot = ph_info["slot"]
        if slot not in market_cards[market] or market_cards[market][slot] is None:
            continue
        if market_cards_locked[market].get(slot):
            continue

        occupied_slots = [s for s, card_id in market_cards[market].items() if card_id is not None]
        if not occupied_slots or slot != max(occupied_slots):
            continue

        rect = ph_info["rect"]
        if rect.collidepoint(mouse_pos):
            return {
                "dragged_card_index": None,
                "dragged_card_source": "market",
                "dragged_card_market": market,
                "dragged_card_market_slot": slot,
                "drag_offset": (mouse_pos[0] - rect.x, mouse_pos[1] - rect.y),
                "dragged_card_pos": mouse_pos,
            }
    return None


def find_side_top_drag_start(mouse_pos, side_placeholders_top, side_cards_top, side_cards_locked_top):
    """Return drag state for the last unlocked right-side top card, or None."""
    occupied = [slot for slot, card_id in enumerate(side_cards_top) if card_id is not None]
    last_slot = max(occupied) if occupied else None
    if last_slot is None:
        return None

    for ph_info in side_placeholders_top:
        slot = ph_info.get("slot")
        if slot is None or slot != last_slot:
            continue
        if side_cards_top[slot] is None or side_cards_locked_top.get(slot):
            continue

        rect = ph_info["rect"]
        if rect.collidepoint(mouse_pos):
            return {
                "dragged_card_source": "side_top",
                "dragged_card_side_slot": slot,
                "drag_offset": (mouse_pos[0] - rect.x, mouse_pos[1] - rect.y),
                "dragged_card_pos": mouse_pos,
            }
    return None


def cleared_drag_state():
    """Return the default idle drag state."""
    return {
        "dragged_card_index": None,
        "dragged_card_source": None,
        "dragged_card_market": None,
        "dragged_card_market_slot": None,
        "dragged_card_side_slot": None,
        "drag_offset": (0, 0),
    }
