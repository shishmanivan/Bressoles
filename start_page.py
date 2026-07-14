import pygame

from asset_loaders import load_scaled_background


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 235, 150)
DARK_GOLD = (184, 134, 11)
PAPER_COLOR = (83, 76, 70)


class StartPage:
    def __init__(self, screen, background, font_path, lang_dict=None, profile_name=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang = lang_dict if lang_dict else {}
        self.profile_name = (profile_name or "").strip()

        start_page_path = "UI/StartPage.jpg"
        self.background = load_scaled_background(
            start_page_path,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            fallback_surface=background,
            warning_message="WARNING: StartPage.jpg not found:",
        )

        self.font_large = pygame.font.Font(font_path, 72)
        self.font_medium = pygame.font.Font(font_path, 48)
        self.font_small = pygame.font.Font(font_path, 36)
        self._text_surface_cache = {}

        self.menu_items = [
            self.lang.get("MenuStart", "Start Game"),
            self.lang.get("MenuOption", "Options"),
            self.lang.get("MenuQuit", "Quit"),
            self.lang.get("MenuTestMode", "Test Mode"),
        ]
        self.selected_index = 0
        self.menu_positions = [
            (SCREEN_WIDTH - 400, 350),
            (SCREEN_WIDTH - 400, 450),
            (SCREEN_WIDTH - 400, 550),
            (SCREEN_WIDTH - 400, 650),
        ]
        self.profile_rect = None

    def _render_text_cached(self, font, text, color):
        cache_key = (id(font), str(text), tuple(color))
        surface = self._text_surface_cache.get(cache_key)
        if surface is None:
            surface = font.render(str(text), True, color)
            self._text_surface_cache[cache_key] = surface
        return surface

    def _get_menu_rect(self, index):
        """Get the clickable rectangle for a menu item."""
        menu_x, y_pos = self.menu_positions[index]
        item = self.menu_items[index]
        text = self._render_text_cached(self.font_medium, item, PAPER_COLOR)
        text_rect = text.get_rect(center=(menu_x, y_pos))
        return text_rect.inflate(20, 10)

    def _get_profile_label(self):
        profile_word = self.lang.get("Profile", "Profile")
        return f"{profile_word}: {self.profile_name}" if self.profile_name else profile_word

    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.selected_index == 0:
                        return "start"
                    if self.selected_index == 1:
                        return "options"
                    if self.selected_index == 2:
                        return "quit"
                    if self.selected_index == 3:
                        return "test_mode"

            if event.type == pygame.MOUSEMOTION:
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    continue
                for i in range(len(self.menu_items)):
                    menu_rect = self._get_menu_rect(i)
                    if menu_rect.collidepoint(mouse_pos):
                        self.selected_index = i
                        break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    return "profile"
                for i in range(len(self.menu_items)):
                    menu_rect = self._get_menu_rect(i)
                    if menu_rect.collidepoint(mouse_pos):
                        if i == 0:
                            return "start"
                        if i == 1:
                            return "options"
                        if i == 2:
                            return "quit"
                        if i == 3:
                            return "test_mode"

        return None

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        profile_label = self._get_profile_label()
        profile_center = (SCREEN_WIDTH - 400, 255)
        profile_hover = self.profile_rect and self.profile_rect.collidepoint(pygame.mouse.get_pos())
        profile_color = LIGHT_GOLD if profile_hover else PAPER_COLOR
        profile_shadow = self._render_text_cached(self.font_medium, profile_label, BLACK)
        profile_text = self._render_text_cached(self.font_medium, profile_label, profile_color)
        profile_shadow_rect = profile_shadow.get_rect(center=(profile_center[0] + 2, profile_center[1] + 2))
        profile_text_rect = profile_text.get_rect(center=profile_center)
        self.profile_rect = profile_text_rect.inflate(24, 12)
        self.screen.blit(profile_shadow, profile_shadow_rect)
        self.screen.blit(profile_text, profile_text_rect)

        for i, item in enumerate(self.menu_items):
            menu_x, y_pos = self.menu_positions[i]
            highlight = i == self.selected_index
            color = LIGHT_GOLD if highlight else PAPER_COLOR

            if highlight:
                indicator = self._render_text_cached(self.font_medium, ">", GOLD)
                rect = indicator.get_rect(center=(menu_x - 100, y_pos))
                self.screen.blit(indicator, rect)

            shadow = self._render_text_cached(self.font_medium, item, BLACK)
            shadow_rect = shadow.get_rect(center=(menu_x + 2, y_pos + 2))
            self.screen.blit(shadow, shadow_rect)

            text = self._render_text_cached(self.font_medium, item, color)
            text_rect = text.get_rect(center=(menu_x, y_pos))
            self.screen.blit(text, text_rect)

        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()

            if result == "quit":
                return "quit"
            if result == "start":
                return "start"
            if result == "profile":
                return "profile"
            if result == "test_mode":
                return "test_mode"

            self.draw()
            self.clock.tick(FPS)
