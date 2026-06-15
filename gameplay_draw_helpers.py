def draw_card_with_effects(
    screen,
    image,
    card_id,
    card_x,
    card_y,
    card_size,
    draw_card_action,
    draw_card_turns,
    turns_remaining=None,
):
    """Draw a gameplay card image plus its action/turn overlays."""
    if card_id is None or image is None:
        return
    screen.blit(image, (card_x, card_y))
    draw_card_action(card_id, card_x, card_y, card_size)
    draw_card_turns(card_id, card_x, card_y, card_size, turns_remaining=turns_remaining)


def draw_dragged_cards(
    screen,
    dragged_card_source,
    dragged_card_index,
    dragged_card_market,
    dragged_card_market_slot,
    dragged_card_side_slot,
    dragged_card_pos,
    drag_offset,
    hand_cards,
    market_cards,
    side_cards_top,
    card_images_bottom,
    card_images_market,
    card_images_side,
    card_size_bottom,
    card_size_market,
    card_size_side,
    market_card_turns,
    draw_card_action,
    draw_card_turns,
):
    """Draw the currently dragged card on top of other gameplay elements."""
    card_x = dragged_card_pos[0] - drag_offset[0]
    card_y = dragged_card_pos[1] - drag_offset[1]

    if dragged_card_source == "hand" and dragged_card_index is not None and dragged_card_index < len(hand_cards):
        card_id = hand_cards[dragged_card_index]
        image = card_images_bottom.get(card_id)
        if image:
            draw_card_with_effects(
                screen,
                image,
                card_id,
                card_x,
                card_y,
                card_size_bottom,
                draw_card_action,
                draw_card_turns,
            )

    if dragged_card_source == "market" and dragged_card_market is not None:
        card_id = market_cards[dragged_card_market].get(dragged_card_market_slot)
        image = card_images_market.get(card_id)
        if image:
            turns_remaining = market_card_turns[dragged_card_market].get(dragged_card_market_slot)
            draw_card_with_effects(
                screen,
                image,
                card_id,
                card_x,
                card_y,
                card_size_market,
                draw_card_action,
                draw_card_turns,
                turns_remaining=turns_remaining,
            )

    if dragged_card_source == "side_top" and dragged_card_side_slot is not None:
        card_id = side_cards_top[dragged_card_side_slot] if 0 <= dragged_card_side_slot < len(side_cards_top) else None
        image = card_images_side.get(card_id) or card_images_market.get(card_id)
        if image:
            draw_card_with_effects(
                screen,
                image,
                card_id,
                card_x,
                card_y,
                card_size_side,
                draw_card_action,
                draw_card_turns,
            )


def draw_hand_compact_animations(
    screen,
    hand_compact_anim,
    card_images_bottom,
    card_size_bottom,
    draw_card_action,
    draw_card_turns,
):
    """Draw cards moving left during hand compaction."""
    for move in hand_compact_anim:
        card_id = move["card_id"]
        image = card_images_bottom.get(card_id)
        if card_id is None or not image:
            continue
        from_x, from_y = move["from_pos"]
        to_x, to_y = move["to_pos"]
        progress = max(0.0, min(1.0, move.get("progress", 0.0)))
        card_x = from_x + (to_x - from_x) * progress - 2
        card_y = from_y + (to_y - from_y) * progress - 2
        draw_card_with_effects(
            screen,
            image,
            card_id,
            card_x,
            card_y,
            card_size_bottom,
            draw_card_action,
            draw_card_turns,
        )


def draw_hand_draw_animations(
    screen,
    hand_draw_anim,
    card_images_bottom,
    card_size_bottom,
    draw_card_action,
    draw_card_turns,
):
    """Draw cards flying into hand after compaction."""
    for draw_entry in hand_draw_anim:
        card_id = draw_entry["card_id"]
        image = card_images_bottom.get(card_id)
        if card_id is None or not image:
            continue
        from_x, from_y = draw_entry["from_pos"]
        to_x, to_y = draw_entry["target_pos"]
        progress = max(0.0, min(1.0, draw_entry.get("progress", 0.0)))
        card_x = from_x + (to_x - from_x) * progress - 2
        card_y = from_y + (to_y - from_y) * progress - 2
        draw_card_with_effects(
            screen,
            image,
            card_id,
            card_x,
            card_y,
            card_size_bottom,
            draw_card_action,
            draw_card_turns,
        )
