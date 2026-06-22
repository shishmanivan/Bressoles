import os
import sys

import pygame

from round_page_assets import load_round_page_static_assets


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

PAPER_COLOR = (83, 76, 70)
BUTTON_COLOR = (238, 228, 205)
BUTTON_HOVER_COLOR = (248, 239, 216)
PANEL_SIZE = (1440, 900)
PANEL_POS = ((SCREEN_WIDTH - PANEL_SIZE[0]) // 2, (SCREEN_HEIGHT - PANEL_SIZE[1]) // 2)


class ShopPage:
    """Intermediate shop screen shown after a completed round."""

    def __init__(self, screen, font_path, napoleondors=0, lang_dict=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.lang_dict = lang_dict or {}
        self.napoleondors = int(napoleondors or 0)

        assets = load_round_page_static_assets()
        self.round_background = assets["background"]
        self.round_koordinates = assets["koordinates"]
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(os.path.join("RoundPage", "SilverBlack.png"), PANEL_SIZE)

        self.title_font = pygame.font.Font(font_path, 72)
        self.balance_font = pygame.font.Font(font_path, 48)
        self.button_font = pygame.font.Font(font_path, 42)
        self.button_rect = pygame.Rect(0, 0, 260, 86)
        self.button_rect.center = (self.panel_rect.centerx, self.panel_rect.bottom - 120)

    def _load_image(self, path, size=None):
        if not os.path.exists(path):
            print(f"WARNING: Shop asset not found: {path}")
            return None
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.smoothscale(image, size).convert_alpha()
        return image

    def _draw_centered_text(self, text, font, center, color=PAPER_COLOR):
        surface = font.render(str(text), True, color)
        rect = surface.get_rect(center=center)
        self.screen.blit(surface, rect)

    def draw(self):
        if self.round_background:
            self.screen.blit(self.round_background, (0, 0))
        else:
            self.screen.fill((235, 220, 190))
        if self.round_koordinates:
            self.screen.blit(self.round_koordinates, (0, 0))

        if self.background:
            self.screen.blit(self.background, self.panel_rect.topleft)
        else:
            pygame.draw.rect(self.screen, (235, 220, 190), self.panel_rect)
            pygame.draw.rect(self.screen, PAPER_COLOR, self.panel_rect, 3)

        self._draw_centered_text("Магазин", self.title_font, (self.panel_rect.centerx, self.panel_rect.y + 150))
        self._draw_centered_text(
            f"Наполеондоры: {self.napoleondors}",
            self.balance_font,
            (self.panel_rect.centerx, self.panel_rect.y + 260),
        )

        mouse_pos = pygame.mouse.get_pos()
        button_color = BUTTON_HOVER_COLOR if self.button_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, self.button_rect, border_radius=8)
        pygame.draw.rect(self.screen, PAPER_COLOR, self.button_rect, 3, border_radius=8)
        self._draw_centered_text("Дальше", self.button_font, self.button_rect.center)

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        return "next"
                    if event.key == pygame.K_ESCAPE:
                        return "next"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.button_rect.collidepoint(event.pos):
                        return "next"

            self.draw()
            self.clock.tick(FPS)
