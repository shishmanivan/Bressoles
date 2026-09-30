"""Descriptions of the three stocks' natural price movements."""
from pathlib import Path

import pygame

from localization import get_language, translate
from shared_utils import wrap_text


STOCK_DESCRIPTIONS = (
    "Акции A сами по себе никогда не падают, растут на 2 доллара. Небольшая вероятность того, что цена не изменится.",
    "Акции B растут и падают на 4 доллара. Большая вероятность роста, небольшая вероятность падения и небольшая вероятность того, что цена не изменится.",
    "Акции C растут и падают на 6 долларов. Существенная вероятность падения. Существенная вероятность того, что цена не изменится. Самые рискованные акции.",
)


def draw_stock_tooltip(screen, market, mouse_pos, font):
    width = min(460, screen.get_width() - 16)
    padding = 18
    lines = wrap_text(translate(STOCK_DESCRIPTIONS[market]), font, width - padding * 2)
    line_height = font.get_linesize() + 4
    panel = pygame.Rect(0, 0, width, padding * 2 + len(lines) * line_height)
    panel.topleft = (mouse_pos[0] + 20, mouse_pos[1] + 20)
    if panel.right > screen.get_width() - 8:
        panel.right = mouse_pos[0] - 20
    panel.clamp_ip(screen.get_rect().inflate(-16, -16))
    pygame.draw.rect(screen, (244, 235, 211), panel, border_radius=8)
    pygame.draw.rect(screen, (83, 76, 70), panel, 3, border_radius=8)
    for index, line in enumerate(lines):
        screen.blit(font.render(line, True, (83, 76, 70)),
                    (panel.left + padding, panel.top + padding + index * line_height))


def stock_tooltip_font(font_path):
    if get_language() == "HU":
        font_path = str(Path(__file__).parent / "Fonts" / "OldStandard-Bold.ttf")
    return pygame.font.Font(font_path, 26)
