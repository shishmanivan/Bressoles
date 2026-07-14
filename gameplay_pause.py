import pygame


INK = (66, 57, 48)
PAPER = (226, 216, 190)
PAPER_DARK = (205, 192, 160)
HOVER = (190, 171, 127)
DANGER = (105, 54, 43)
SHADOW = (24, 20, 17, 175)


def build_pause_menu_layout(screen_size, confirmation=False):
    screen_width, screen_height = screen_size
    panel_width = min(620, max(480, screen_width - 80))
    panel_height = 500 if not confirmation else 440
    panel_height = min(panel_height, screen_height - 60)
    panel = pygame.Rect(
        (screen_width - panel_width) // 2,
        (screen_height - panel_height) // 2,
        panel_width,
        panel_height,
    )

    button_width = panel_width - 120
    button_height = 74
    button_x = panel.centerx - button_width // 2
    if confirmation:
        actions = ("cancel", "restart_confirm")
        first_y = panel.top + 238
    else:
        actions = ("continue", "save_exit", "restart")
        first_y = panel.top + 145

    buttons = {
        action: pygame.Rect(button_x, first_y + index * 90, button_width, button_height)
        for index, action in enumerate(actions)
    }
    return {"panel": panel, "buttons": buttons, "confirmation": bool(confirmation)}


def get_pause_menu_action(layout, position):
    for action, rect in layout.get("buttons", {}).items():
        if rect.collidepoint(position):
            return action
    return None


def _draw_centered_text(surface, font, text, color, center_x, y):
    rendered = font.render(str(text), True, color)
    surface.blit(rendered, (center_x - rendered.get_width() // 2, y))


def draw_pause_menu(surface, layout, texts, title_font, button_font, small_font, mouse_pos):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 142))
    surface.blit(overlay, (0, 0))

    panel = layout["panel"]
    shadow_rect = panel.move(10, 12)
    shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    shadow.fill(SHADOW)
    surface.blit(shadow, shadow_rect)

    pygame.draw.rect(surface, PAPER, panel)
    pygame.draw.rect(surface, INK, panel, 4)
    pygame.draw.rect(surface, INK, panel.inflate(-18, -18), 1)

    if layout["confirmation"]:
        title = texts["restart_confirm"]
        warning = texts["restart_warning"]
    else:
        title = texts["title"]
        warning = None

    _draw_centered_text(surface, title_font, title, INK, panel.centerx, panel.top + 34)
    rule_y = panel.top + 107
    pygame.draw.line(surface, INK, (panel.left + 54, rule_y), (panel.right - 54, rule_y), 2)
    pygame.draw.line(surface, INK, (panel.left + 80, rule_y + 7), (panel.right - 80, rule_y + 7), 1)

    if warning:
        _draw_centered_text(surface, small_font, warning, INK, panel.centerx, panel.top + 155)

    labels = {
        "continue": texts["continue"],
        "save_exit": texts["save_exit"],
        "restart": texts["restart"],
        "cancel": texts["cancel"],
        "restart_confirm": texts["restart"],
    }
    for action, rect in layout["buttons"].items():
        hovered = rect.collidepoint(mouse_pos)
        fill = HOVER if hovered else PAPER_DARK
        border = DANGER if action in ("restart", "restart_confirm") else INK
        pygame.draw.rect(surface, fill, rect, border_radius=2)
        pygame.draw.rect(surface, border, rect, 3, border_radius=2)
        label = button_font.render(labels[action], True, INK)
        label_rect = label.get_rect(center=rect.center)
        surface.blit(label, label_rect)
