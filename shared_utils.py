DEFAULT_WRAP_TEXT_COLOR = (83, 76, 70)


def _clamp_dt_seconds(dt: float, max_dt: float = 0.05) -> float:
    """Clamp dt to avoid big jumps after window focus loss / stutters."""
    if dt < 0:
        return 0.0
    if dt > max_dt:
        return max_dt
    return dt


def move_towards(current: float, target: float, max_delta: float) -> float:
    """Move current towards target by at most max_delta."""
    if max_delta <= 0:
        return current
    delta = target - current
    if abs(delta) <= max_delta:
        return target
    return current + max_delta if delta > 0 else current - max_delta


def clamp_popup_y(desired_y: float, popup_image, screen_height: int, margin: float = 10.0) -> float:
    """Clamp popup top-left Y so the popup stays fully visible on screen."""
    if popup_image is None:
        return float(desired_y)
    try:
        popup_h = float(popup_image.get_height())
    except Exception:
        return float(desired_y)
    if popup_h <= 0:
        return float(desired_y)
    min_y = float(margin)
    max_y = float(screen_height) - popup_h - float(margin)
    if max_y < min_y:
        max_y = min_y
    return float(max(min_y, min(float(desired_y), max_y)))


def wrap_text(text, font, max_width, color=DEFAULT_WRAP_TEXT_COLOR):
    """Split text into lines that fit within max_width using rendered widths."""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        candidate = " ".join(current_line + [word]) if current_line else word
        candidate_width = font.render(candidate + " ", True, color).get_width()
        if candidate_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines
