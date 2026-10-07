"""Shared collection window and compact, clipped deck grid."""
import math
import pygame

INK = (85, 73, 55)
ACCENT = (170, 130, 66)
CARD_SIZE = (87, 150)


def panel_rect(size):
    width, height = size
    return pygame.Rect(int(width * .1), int(height * .1), int(width * .8), int(height * .75))


def draw_panel(screen, panel, background):
    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 85))
    screen.blit(dim, (0, 0))
    if background is not None:
        screen.blit(background, panel)
    else:
        pygame.draw.rect(screen, (241, 232, 210), panel)
    pygame.draw.rect(screen, INK, panel, 3)


def deck_layout(content, sections, card_size=CARD_SIZE, extra_height=0):
    """Return headers and indexed card rectangles, preserving duplicate identity."""
    width, height = card_size
    step_x, step_y = width + 22, height + 18 + extra_height
    columns = max(1, (content.width + 22) // step_x)
    left = content.centerx - (columns * step_x - 22) // 2
    top = 0
    headers, entries = [], []
    for label, cards in sections:
        if not cards:
            continue
        if label:
            headers.append((label, (left, content.y + top)))
            top += 36
        for position, (index, card) in enumerate(cards):
            rect = pygame.Rect(left + position % columns * step_x,
                               content.y + top + position // columns * step_y, width, height)
            entries.append((index, card, rect))
        top += math.ceil(len(cards) / columns) * step_y
    return headers, entries, top


def draw_grid(screen, content, headers, entries, offset, font, draw_card, extra_height=0):
    old_clip = screen.get_clip()
    screen.set_clip(content.clip(old_clip))
    visible = []
    try:
        for label, (x, y) in headers:
            screen.blit(font.render(label, True, INK), (x, y - offset))
        for index, card, original in entries:
            rect = original.move(0, -offset)
            hit_rect = rect.copy()
            hit_rect.height += extra_height
            if not hit_rect.colliderect(content):
                continue
            draw_card(index, card, rect)
            visible.append((index, card, hit_rect.clip(content)))
    finally:
        screen.set_clip(old_clip)
    return visible


def draw_scrollbar(screen, panel, content, offset, maximum):
    if maximum <= 0:
        return
    track = pygame.Rect(panel.right - 19, content.top, 5, content.height)
    pygame.draw.rect(screen, (204, 191, 168), track, border_radius=2)
    height = max(30, round(track.height * content.height / (content.height + maximum)))
    top = track.top + round((track.height - height) * offset / maximum)
    pygame.draw.rect(screen, ACCENT, (track.x, top, track.width, height), border_radius=2)
