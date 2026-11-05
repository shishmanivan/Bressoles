"""Condition medallions above the round-selection route."""

import native_render as pygame

from asset_loaders import load_scaled_image
from gameplay_conditions import CONDITIONS, conditions_for_level
from localization import translate
from shared_utils import wrap_text


ICON_SIZE = 100
HOVER_SIZE = 110
ICON_TOP = 24
CELL_WIDTH = 200
# Apparent face width at each pose in the boss hover sequence.
FACE_WIDTH = (1.0, 0.87, 0.5, 0.12, 0.87, 0.5, 0.12)


def draw_condition_icons(page):
    # Round selection shows level rules, before the player equips round-specific cards.
    condition_ids = conditions_for_level(page.level_number)
    page.condition_icon_rects = {}
    page.condition_tooltip_rect = None
    previous_hover = getattr(page, "hovered_condition", None)
    page.hovered_condition = None
    if not condition_ids:
        return
    font = getattr(page, "condition_icon_font", None)
    if font is None:
        font = page.condition_icon_font = pygame.font.Font(page.font_path, 22)
    first_center = 24 + CELL_WIDTH // 2
    mouse_x, mouse_y = page.mouse_pos()
    hovered = None
    for index, condition_id in enumerate(condition_ids):
        definition = CONDITIONS[condition_id]
        center_x = first_center + index * CELL_WIDTH
        rect = pygame.Rect(center_x - ICON_SIZE // 2, ICON_TOP, ICON_SIZE, ICON_SIZE)
        # Use the original circle for hit testing so enlargement never flickers at the edge.
        is_hovered = (mouse_x - rect.centerx) ** 2 + (mouse_y - rect.centery) ** 2 <= (ICON_SIZE // 2) ** 2
        size = HOVER_SIZE if is_hovered else ICON_SIZE
        width = size
        if is_hovered:
            now = pygame.time.get_ticks()
            if previous_hover != condition_id:
                page.condition_hover_start = now
            step = (now - page.condition_hover_start) // page.animation_frame_duration
            pose = page.animation_sequence[step % len(page.animation_sequence)]
            width = max(1, round(size * FACE_WIDTH[pose]))
        icon = load_scaled_image(definition["icon"], target_size=(width, size))
        if icon is not None:
            page.screen.blit(icon, icon.get_rect(center=rect.center))
        page.condition_icon_rects[condition_id] = rect
        title_lines = wrap_text(translate(definition["title"]), font, CELL_WIDTH - 12)
        for row, line in enumerate(title_lines):
            label = font.render(line, True, (83, 76, 70))
            page.screen.blit(label, label.get_rect(midtop=(center_x, rect.bottom + 8 + row * font.get_linesize())))
        if is_hovered:
            hovered = (condition_id, center_x, rect.bottom + 12 + len(title_lines) * font.get_linesize())
    if hovered is not None:
        condition_id, center_x, tooltip_top = hovered
        definition = CONDITIONS[condition_id]
        text = translate(definition.get("tooltip", definition["paragraphs"][0]))
        width = min(500, page.screen.get_width() - 32)
        padding = 18
        lines = wrap_text(text, font, width - padding * 2)
        line_height = font.get_linesize() + 4
        panel = pygame.Rect(0, 0, width, len(lines) * line_height + padding * 2)
        panel.midtop = (center_x, tooltip_top)
        panel.clamp_ip(page.screen.get_rect().inflate(-24, -24))
        pygame.draw.rect(page.screen, (241, 227, 196), panel, border_radius=10)
        pygame.draw.rect(page.screen, (105, 92, 78), panel, 2, border_radius=10)
        for row, line in enumerate(lines):
            label = font.render(line, True, (83, 76, 70))
            page.screen.blit(label, (panel.x + padding, panel.y + padding + row * line_height))
        page.condition_tooltip_rect = panel
        page.hovered_condition = condition_id
