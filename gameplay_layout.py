import pygame


def compute_bottom_hand_layout(bottom_frame, hand, screen_width, screen_height, y_offset=10):
    """Compute bottom hand frame and slot geometry used by GameplayPage."""
    if not bottom_frame or hand <= 0:
        return None

    frame_width = bottom_frame.get_width()
    frame_height = bottom_frame.get_height()
    frame_x = (screen_width - frame_width) // 2 - 200
    frame_y = screen_height - frame_height - 150

    placeholder_width = 138
    placeholder_height = 240
    margin_x = 20
    available_width = max(placeholder_width, frame_width - margin_x * 2)
    if hand > 1:
        base_spacing = (frame_width - placeholder_width * hand) / (hand + 1)
        normal_step = placeholder_width + (base_spacing * 0.7)
        fit_step = (available_width - placeholder_width) / (hand - 1)
        step = min(normal_step, fit_step)
    else:
        step = 0
    spacing = step - placeholder_width if hand > 1 else 0
    total_width = placeholder_width + step * (hand - 1)
    start_x = frame_x + (frame_width - total_width) / 2
    start_y = frame_y + (frame_height - placeholder_height) // 2 + y_offset

    slot_positions = []
    slot_rects = []
    for slot in range(hand):
        slot_x = start_x + slot * (placeholder_width + spacing)
        slot_y = start_y
        slot_positions.append((slot_x, slot_y))
        slot_rects.append(pygame.Rect(slot_x, slot_y, placeholder_width, placeholder_height))

    return {
        "frame_width": frame_width,
        "frame_height": frame_height,
        "frame_x": frame_x,
        "frame_y": frame_y,
        "placeholder_width": placeholder_width,
        "placeholder_height": placeholder_height,
        "spacing": spacing,
        "start_x": start_x,
        "start_y": start_y,
        "slot_positions": slot_positions,
        "slot_rects": slot_rects,
    }


def build_bottom_placeholders(layout):
    """Convert a bottom hand layout into GameplayPage placeholder records."""
    if not layout:
        return []
    return [
        {"slot": slot, "rect": rect}
        for slot, rect in enumerate(layout["slot_rects"])
    ]


def compute_market_frames_layout(frame, screen_width, top_y=40, spacing=10, x_offset=-200):
    """Compute the three market frame positions used by GameplayPage."""
    if not frame:
        return None

    frame_width = frame.get_width()
    frame_height = frame.get_height()
    total_width = (frame_width * 3) + (spacing * 2)
    start_x = (screen_width - total_width) // 2 + x_offset

    frame_rects = []
    for market in range(3):
        frame_x = start_x + market * (frame_width + spacing)
        frame_rects.append(
            {
                "market": market,
                "x": frame_x,
                "y": top_y,
                "rect": pygame.Rect(frame_x, top_y, frame_width, frame_height),
            }
        )

    return {
        "frame_width": frame_width,
        "frame_height": frame_height,
        "spacing": spacing,
        "start_x": start_x,
        "frame_rects": frame_rects,
    }


def compute_right_panel_layout(
    market_layout,
    screen_width,
    screen_height,
    side_placeholder,
    bottom_frame=None,
    desired_top_y=None,
    bottom_slots=3,
):
    """Compute right-side panel frame geometry used by GameplayPage."""
    if not market_layout:
        return None

    frame_width = market_layout["frame_width"]
    frame_height = market_layout["frame_height"]
    frame_c_rect = market_layout["frame_rects"][2]["rect"]
    right_frame_x = min(frame_c_rect.right + 20, screen_width - 20 - frame_width)

    side_ph_w = side_placeholder.get_width() if side_placeholder else 96
    side_ph_h = side_placeholder.get_height() if side_placeholder else 168
    top_rows = 2
    bottom_rows = 1
    min_pad = 18
    right_top_y_base = 40
    right_top_h_base = max(frame_height, top_rows * side_ph_h + (top_rows + 1) * min_pad)
    right_top_bottom = right_top_y_base + right_top_h_base

    right_bot_h = side_ph_h + 24
    if bottom_frame:
        right_bot_y = screen_height - bottom_frame.get_height() - 150 + 17
    else:
        right_bot_y = right_top_bottom + 20

    if desired_top_y is None:
        right_top_y = right_top_y_base
    else:
        min_pad_top = 12
        min_top_h = top_rows * side_ph_h + (top_rows + 1) * min_pad_top
        right_top_y = min(desired_top_y, right_top_bottom - min_top_h)

    right_top_h = max(1, right_top_bottom - right_top_y)

    return {
        "x": right_frame_x,
        "width": frame_width,
        "top_y": right_top_y,
        "top_height": right_top_h,
        "bottom_y": right_bot_y,
        "bottom_height": right_bot_h,
        "label_start_x": right_frame_x + 10,
        "top_rows": top_rows,
        "bottom_rows": bottom_rows,
        "bottom_slots": max(1, int(bottom_slots or 3)),
    }


def build_market_placeholders(frame_rect, market, placeholder_width=96, placeholder_height=168):
    """Build placeholder records for one market frame."""
    num_placeholders = 3
    spacing = (frame_rect.width - placeholder_width * num_placeholders) / (num_placeholders + 1)
    ph_start_x = frame_rect.x + spacing
    ph_start_y = frame_rect.y + frame_rect.height - placeholder_height - 30

    placeholders = []
    for slot in range(num_placeholders):
        ph_x = ph_start_x + slot * (placeholder_width + spacing)
        if slot == 0:
            ph_x += 7
        elif slot == 2:
            ph_x -= 7
        rect = pygame.Rect(ph_x, ph_start_y, placeholder_width, placeholder_height)
        placeholders.append({"market": market, "slot": slot, "rect": rect})
    return placeholders


def build_side_panel_placeholders(right_panel_layout, placeholder_image):
    """Build top and bottom placeholder records for the right-side panel."""
    if not right_panel_layout or not placeholder_image:
        return [], []

    ph_w = placeholder_image.get_width()
    ph_h = placeholder_image.get_height()
    frame_x = right_panel_layout["x"]
    frame_w = right_panel_layout["width"]

    top_placeholders = []
    cols = 3
    rows = right_panel_layout["top_rows"]
    pad_x = max(10.0, (frame_w - cols * ph_w) / (cols + 1))
    pad_y = max(10.0, (right_panel_layout["top_height"] - rows * ph_h) / (rows + 1))
    for row in range(rows):
        for col in range(cols):
            x = frame_x + pad_x * (col + 1) + ph_w * col
            y = right_panel_layout["top_y"] + pad_y * (row + 1) + ph_h * row
            rect = pygame.Rect(int(round(x)), int(round(y)), ph_w, ph_h)
            top_placeholders.append({"slot": row * cols + col, "rect": rect})

    bottom_placeholders = []
    rows = right_panel_layout["bottom_rows"]
    bottom_slots = max(1, int(right_panel_layout.get("bottom_slots", cols) or cols))
    pad_y = max(10.0, (right_panel_layout["bottom_height"] - rows * ph_h) / (rows + 1))
    if bottom_slots <= cols:
        pad_x = max(10.0, (frame_w - cols * ph_w) / (cols + 1))
        x_positions = [frame_x + pad_x * (col + 1) + ph_w * col for col in range(bottom_slots)]
    else:
        side_margin = 10.0
        available_width = max(ph_w, frame_w - side_margin * 2)
        step = (available_width - ph_w) / max(1, bottom_slots - 1)
        total_width = ph_w + step * (bottom_slots - 1)
        start_x = frame_x + (frame_w - total_width) / 2
        x_positions = [start_x + step * col for col in range(bottom_slots)]
    for col, x in enumerate(x_positions):
        y = right_panel_layout["bottom_y"] + pad_y
        rect = pygame.Rect(int(round(x)), int(round(y)), ph_w, ph_h)
        bottom_placeholders.append({"slot": col, "rect": rect})

    return top_placeholders, bottom_placeholders
