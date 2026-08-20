import pygame

from asset_loaders import load_scaled_background


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 235, 150)
PAPER_COLOR = (83, 76, 70)
TRACK_COLOR = (112, 94, 69)
TRACK_EMPTY_COLOR = (181, 158, 119)


class SettingsPage:
    def __init__(self, screen, background, font_path, lang_dict=None, music_volume=1.0, on_volume_change=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang = lang_dict or {}
        self.on_volume_change = on_volume_change
        self.music_volume = self._clamp_volume(music_volume)
        self.dragging_volume = False

        self.background = load_scaled_background(
            "UI/StartPage.jpg",
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            fallback_surface=background,
        )
        self.title_font = pygame.font.Font(font_path, 64)
        self.label_font = pygame.font.Font(font_path, 42)
        self.value_font = pygame.font.Font(font_path, 34)
        self.button_font = pygame.font.Font(font_path, 44)

        self.slider_rect = pygame.Rect(1030, 465, 420, 12)
        self.slider_hit_rect = self.slider_rect.inflate(20, 44)
        self.back_rect = pygame.Rect(1110, 610, 260, 70)

    @staticmethod
    def _clamp_volume(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 1.0

    def _set_volume(self, value):
        normalized = self._clamp_volume(value)
        if abs(normalized - self.music_volume) < 0.0001:
            return
        self.music_volume = normalized
        if self.on_volume_change:
            self.on_volume_change(normalized)

    def _set_volume_from_x(self, mouse_x):
        ratio = (float(mouse_x) - self.slider_rect.left) / self.slider_rect.width
        self._set_volume(ratio)

    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
                if event.key in (pygame.K_LEFT, pygame.K_DOWN):
                    self._set_volume(round(self.music_volume * 20 - 1) / 20)
                elif event.key in (pygame.K_RIGHT, pygame.K_UP):
                    self._set_volume(round(self.music_volume * 20 + 1) / 20)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "back"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.slider_hit_rect.collidepoint(mouse_pos):
                    self.dragging_volume = True
                    self._set_volume_from_x(mouse_pos[0])
                elif self.back_rect.collidepoint(mouse_pos):
                    return "back"
            if event.type == pygame.MOUSEMOTION and self.dragging_volume:
                self._set_volume_from_x(mouse_pos[0])
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging_volume = False
        return None

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        center_x = self.slider_rect.centerx
        title = self.title_font.render(self.lang.get("SettingsTitle", "Настройки"), True, PAPER_COLOR)
        self.screen.blit(title, title.get_rect(center=(center_x, 300)))

        label = self.label_font.render(self.lang.get("MusicVolume", "Громкость музыки"), True, PAPER_COLOR)
        self.screen.blit(label, label.get_rect(center=(center_x, 395)))

        pygame.draw.rect(self.screen, TRACK_EMPTY_COLOR, self.slider_rect, border_radius=6)
        filled_width = int(round(self.slider_rect.width * self.music_volume))
        if filled_width > 0:
            filled_rect = pygame.Rect(self.slider_rect.left, self.slider_rect.top, filled_width, self.slider_rect.height)
            pygame.draw.rect(self.screen, TRACK_COLOR, filled_rect, border_radius=6)
        knob_x = self.slider_rect.left + filled_width
        pygame.draw.circle(self.screen, GOLD, (knob_x, self.slider_rect.centery), 18)
        pygame.draw.circle(self.screen, PAPER_COLOR, (knob_x, self.slider_rect.centery), 18, 2)

        value_text = self.value_font.render(f"{round(self.music_volume * 100)}%", True, PAPER_COLOR)
        self.screen.blit(value_text, value_text.get_rect(center=(center_x, 535)))

        hovered = self.back_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, (225, 204, 165), self.back_rect, border_radius=8)
        pygame.draw.rect(self.screen, GOLD if hovered else PAPER_COLOR, self.back_rect, 3, border_radius=8)
        back_text = self.button_font.render(self.lang.get("SettingsBack", "Назад"), True, PAPER_COLOR)
        self.screen.blit(back_text, back_text.get_rect(center=self.back_rect.center))
        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()
            if result in ("back", "quit"):
                return result, self.music_volume
            self.draw()
            self.clock.tick(FPS)
