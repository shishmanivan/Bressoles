import pygame


def _to_rect(value):
    if isinstance(value, pygame.Rect):
        return value.copy()
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return pygame.Rect(*(int(part) for part in value))
    except (TypeError, ValueError):
        return None


def _normalize_lines(lines):
    normalized = []
    for line in lines or []:
        if isinstance(line, (list, tuple)) and len(line) == 4:
            normalized.append(tuple(line))
    return normalized


def _round_progress_key(defeated_count, boss_index, boss_filename):
    normalized_index = boss_index if boss_index is not None else ""
    return f"{int(defeated_count or 0)}:{normalized_index}:{boss_filename or ''}"


def infer_boss_choice_metadata(bp_state, defeated_count, boss_index):
    """Recreate deterministic BossPage geometry for legacy partial saves."""
    try:
        normalized_defeated = max(0, int(defeated_count or 0))
        normalized_index = max(0, int(boss_index or 0))
    except (TypeError, ValueError):
        return None, []

    previous_rect = _to_rect(bp_state.get("last_rect"))
    if normalized_defeated > 0 and previous_rect:
        start_x, start_y = previous_rect.center
        end_x = start_x + 200
        end_y = start_y - 150 * (normalized_index + 1)
    else:
        start_x, start_y = 235, 832
        end_x = 400
        end_y = 700 - 150 * normalized_index

    clicked_rect = pygame.Rect(end_x - 50, end_y - 50, 100, 100)
    saved_lines = _normalize_lines(bp_state.get("lines"))
    current_line = (start_x, start_y, end_x, end_y)
    if not saved_lines or saved_lines[-1] != current_line:
        saved_lines.append(current_line)
    return clicked_rect, saved_lines


def remember_current_boss(bp_state, defeated_count, boss_index, boss_filename, boss_page=None):
    """Store the active encounter without discarding map metadata on resume."""
    try:
        normalized_index = int(boss_index)
    except (TypeError, ValueError):
        normalized_index = 0
    normalized_defeated = int(defeated_count or 0)

    existing = bp_state.get("current_boss")
    if not isinstance(existing, dict):
        existing = {}
    same_encounter = (
        int(existing.get("defeated_count", -1) or 0) == normalized_defeated
        and int(existing.get("boss_index", -1) or 0) == normalized_index
        and existing.get("boss_filename") == boss_filename
    )
    if not same_encounter:
        existing = {}

    if boss_page is not None:
        clicked_filename = getattr(boss_page, "clicked_boss_filename", None) or boss_filename
        clicked_rect = getattr(boss_page, "clicked_boss_rect", None)
        saved_lines = getattr(boss_page, "saved_lines", None)
    else:
        clicked_filename = existing.get("clicked_boss_filename") or boss_filename
        clicked_rect = existing.get("clicked_boss_rect")
        saved_lines = existing.get("saved_lines")

    if clicked_rect is None or not saved_lines:
        inferred_rect, inferred_lines = infer_boss_choice_metadata(
            bp_state,
            normalized_defeated,
            normalized_index,
        )
        if clicked_rect is None:
            clicked_rect = inferred_rect
        if not saved_lines:
            saved_lines = inferred_lines

    normalized_rect = _to_rect(clicked_rect)
    context = {
        "defeated_count": normalized_defeated,
        "boss_index": normalized_index,
        "boss_filename": boss_filename,
        "clicked_boss_filename": clicked_filename,
        "clicked_boss_rect": (
            [normalized_rect.x, normalized_rect.y, normalized_rect.width, normalized_rect.height]
            if normalized_rect
            else None
        ),
        "saved_lines": _normalize_lines(saved_lines),
    }
    bp_state["current_boss"] = context
    return context


def complete_boss_position(bp_state, boss_context, boss_page=None):
    """Apply the map/progress transition after a boss victory."""
    context = dict(boss_context or {})
    defeated_count = int(context.get("defeated_count", bp_state.get("defeated", 0)) or 0)
    boss_index = context.get("boss_index")
    boss_filename = context.get("boss_filename")

    if boss_page is not None:
        saved_lines = getattr(boss_page, "saved_lines", None)
        clicked_rect = getattr(boss_page, "clicked_boss_rect", None)
        clicked_filename = getattr(boss_page, "clicked_boss_filename", None)
    else:
        saved_lines = None
        clicked_rect = None
        clicked_filename = None

    if saved_lines is None:
        saved_lines = context.get("saved_lines") or []
    if clicked_rect is None:
        clicked_rect = context.get("clicked_boss_rect")
    if not clicked_filename:
        clicked_filename = context.get("clicked_boss_filename") or boss_filename

    normalized_rect = _to_rect(clicked_rect)
    bp_state["defeated"] = max(int(bp_state.get("defeated", 0) or 0), defeated_count + 1)
    if normalized_rect:
        bp_state["last_rect"] = normalized_rect.copy()
    normalized_lines = _normalize_lines(saved_lines)
    if normalized_lines:
        bp_state["lines"] = normalized_lines

    defeated_bosses = bp_state.setdefault("defeated_bosses", [])
    if clicked_filename and normalized_rect:
        already_recorded = any(
            item.get("filename") == clicked_filename and _to_rect(item.get("rect")) == normalized_rect
            for item in defeated_bosses
            if isinstance(item, dict)
        )
        if not already_recorded:
            defeated_bosses.append({"filename": clicked_filename, "rect": normalized_rect.copy()})

    progress_key = _round_progress_key(defeated_count, boss_index, boss_filename)
    bp_state.setdefault("round_progress", {}).pop(progress_key, None)
    bp_state["current_boss"] = None
    return bp_state
