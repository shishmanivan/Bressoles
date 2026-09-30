"""Profile-scoped onboarding shown over the first playable screen."""

from pathlib import Path

import pygame

from gameplay_assets import build_hand_frame
from localization import get_language, translate
from shared_utils import wrap_text


FIRST_HINT_ID = "stock_cards"
FIRST_HINT_TEXT = (
    "Акции растут и падают. "
    "Влияйте на рост и падение цен с помощью карт."
)
SELL_HINT_ID = "sell_before_last_turn"
LOGO_HINT_ID = "stock_logo_hover"
LOGO_HINT_TEXT = "Наведите мышь на логотип акции для того, чтобы узнать более подробную информацию."
SELL_HINT_TEXT = (
    "Перед последним ходом вы должны обналичить свои акции. "
    "Карты, позволяющие автоматически продавать акции на последнем ходу, появятся позже. "
    "Пока их нет, продавать акции нужно вручную."
)
INK = (83, 76, 70)


class TutorialHint:
    def __init__(self, screen_size, frame, font_path, ok_image=None,
                 hint_id=FIRST_HINT_ID, text=FIRST_HINT_TEXT):
        self.hint_id = hint_id
        self.has_checkbox = hint_id != FIRST_HINT_ID
        self.dont_show_again = False
        self.panel = pygame.Rect(0, 0, 760, 470 if self.has_checkbox else 340)
        self.panel.center = (screen_size[0] // 2, screen_size[1] // 2)
        self.frame = build_hand_frame(frame, self.panel.size) if frame is not None else None
        # The legacy display font renders Hungarian double accents as blanks.
        if get_language() == "HU":
            font_path = str(Path(__file__).parent / "Fonts" / "OldStandard-Bold.ttf")
        self.font = pygame.font.Font(font_path, 32)
        self.lines = wrap_text(translate(text), self.font, self.panel.width - 120)
        self.ok_image = ok_image
        self.button = pygame.Rect(0, 0, 100, 52)
        if ok_image is not None:
            self.button.size = ok_image.get_size()
        self.button.midbottom = (self.panel.centerx, self.panel.bottom - 35)
        self.checkbox_font = pygame.font.Font(font_path, 26)
        self.checkbox_label = self.checkbox_font.render(translate("Больше не показывать"), True, INK)
        row_width = 28 + 14 + self.checkbox_label.get_width()
        self.checkbox_row = pygame.Rect(0, 0, row_width, 32)
        self.checkbox_row.midbottom = (self.panel.centerx, self.button.top - 20)
        self.checkbox = pygame.Rect(self.checkbox_row.left, self.checkbox_row.top + 2, 28, 28)

    def accepts(self, event):
        if (self.has_checkbox and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.checkbox_row.collidepoint(event.pos)):
            self.dont_show_again = not self.dont_show_again
            return False
        return (
            event.type == pygame.KEYDOWN
            and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)
        ) or (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.button.collidepoint(event.pos)
        )

    def draw(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 110))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (236, 226, 201), self.panel.inflate(-18, -18))
        if self.frame is not None:
            screen.blit(self.frame, self.panel)
        else:
            pygame.draw.rect(screen, INK, self.panel, 3)
        line_height = self.font.get_linesize() + 8
        text_bottom = self.checkbox_row.top if self.has_checkbox else self.button.top
        text_area = pygame.Rect(self.panel.left, self.panel.top + 45,
                                self.panel.width, text_bottom - self.panel.top - 65)
        y = text_area.centery - len(self.lines) * line_height // 2
        for line in self.lines:
            rendered = self.font.render(line, True, INK)
            screen.blit(rendered, (self.panel.centerx - rendered.get_width() // 2, y))
            y += line_height
        if self.has_checkbox:
            pygame.draw.rect(screen, INK, self.checkbox, 2)
            if self.dont_show_again:
                pygame.draw.lines(screen, INK, False, [
                    (self.checkbox.left + 5, self.checkbox.centery),
                    (self.checkbox.left + 11, self.checkbox.bottom - 6),
                    (self.checkbox.right - 5, self.checkbox.top + 6),
                ], 3)
            screen.blit(self.checkbox_label, (self.checkbox.right + 14, self.checkbox_row.top))
        if self.ok_image is not None:
            screen.blit(self.ok_image, self.button)
        else:
            pygame.draw.rect(screen, INK, self.button, 2)
            label = self.font.render("OK", True, INK)
            screen.blit(label, label.get_rect(center=self.button.center))
