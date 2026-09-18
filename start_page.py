import os
from dataclasses import dataclass

import pygame

from adaptive_ui import AnchoredElement, clamp, cover_geometry, proportional_size
from sound_assets import load_sound


FPS = 60
BLACK = (0, 0, 0)
# Median dark ink sampled from the lettering on the ribbon beneath the sack.
PAPER_COLOR = (77, 63, 50)
LIGHT_GOLD = PAPER_COLOR
MENU_TEXT_OPACITY = 255
MENU_HOVER_SCALE = 1.02
PRESS_DURATION_MS = 90
MENU_TEXT_SCALE_X = 0.90

MASTER_BACKGROUND_PATH = os.path.join("UI", "Master Background.png")
TITLE_PATH = os.path.join("UI", "Bressoles Title.png")
MENU_IMAGE_PATH = os.path.join("UI", "Menu3_1.png")
MENU_FONT_PATH = os.path.join("Fonts", "YesevaOne-Regular.ttf")


@dataclass(frozen=True)
class StartPageLayout:
    """All main-menu geometry, calculated only from the current viewport."""

    viewport_size: tuple
    title_rect: pygame.Rect
    menu_image_rect: pygame.Rect
    menu_rect: pygame.Rect
    row_centers: tuple
    font_size: int


def build_start_page_layout(viewport_size, title_source_size, menu_source_size):
    """Build the viewport-anchored equivalent of CSS clamp-based layout rules."""
    viewport_width, viewport_height = viewport_size

    horizontal_margin = round(clamp(24, viewport_width * 0.04, 90))
    title_top = round(clamp(36, viewport_height * 0.07, 100))
    title_width = round(clamp(320, viewport_width * 0.36, 760))
    title_size = proportional_size(title_source_size, width=title_width)
    title_rect = AnchoredElement(
        "left", "top", x_margin=horizontal_margin, y_margin=title_top
    ).rect(title_size, viewport_size)

    # Menu3 is a complete 16:9 composition. Fit it as large as possible without
    # distortion; the cover-rendered master remains visible only where the
    # viewport aspect ratio differs from the artwork.
    menu_scale = min(
        viewport_width / menu_source_size[0],
        viewport_height / menu_source_size[1],
    )
    menu_image_size = (
        max(1, round(menu_source_size[0] * menu_scale)),
        max(1, round(menu_source_size[1] * menu_scale)),
    )
    menu_image_rect = AnchoredElement("center", "center").rect(
        menu_image_size, viewport_size
    )

    # Bounds of the empty ornamental frame inside the native Menu3 artwork.
    frame_left, frame_top, frame_width, frame_height = (1035, 269, 485, 461)
    source_width, source_height = menu_source_size
    menu_rect = pygame.Rect(
        menu_image_rect.left + round(menu_image_rect.width * frame_left / source_width),
        menu_image_rect.top + round(menu_image_rect.height * frame_top / source_height),
        round(menu_image_rect.width * frame_width / source_width),
        round(menu_image_rect.height * frame_height / source_height),
    )

    row_ratios = (0.119, 0.317, 0.510, 0.701, 0.892)
    row_centers = tuple(
        (menu_rect.centerx, menu_rect.top + round(menu_rect.height * ratio))
        for ratio in row_ratios
    )
    # Menu typography stays deliberately substantial even when the decorative
    # frame is compact. Long profile names are fitted separately at draw time.
    font_size = round(clamp(24, menu_rect.height * 0.09, 50))
    return StartPageLayout(
        viewport_size=tuple(viewport_size),
        title_rect=title_rect,
        menu_image_rect=menu_image_rect,
        menu_rect=menu_rect,
        row_centers=row_centers,
        font_size=font_size,
    )


class StartPage:
    def __init__(self, screen, background, font_path, lang_dict=None, profile_name=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang = lang_dict if lang_dict else {}
        self.profile_name = (profile_name or "").strip()
        self.font_path = MENU_FONT_PATH if os.path.exists(MENU_FONT_PATH) else font_path

        self.master_background = self._load_image(
            MASTER_BACKGROUND_PATH, alpha=False, fallback=background
        )
        self.title_image = self._load_image(TITLE_PATH, alpha=True)
        self.menu_image = self._load_image(MENU_IMAGE_PATH, alpha=True)
        self.button_sound = load_sound(os.path.join("Sounds", "Cliack3.wav"))

        self._scaled_image_cache = {}
        self._font_cache = {}
        self._text_surface_cache = {}
        self._bevel_cache = {}
        self._pending_action = None
        self._pressed_target = None
        self._keyboard_focus = False
        self._layout = None

        self.menu_items = [
            self.lang.get("MenuStart", "Start Game"),
            self.lang.get("MenuOption", "Options"),
            self.lang.get("MenuQuit", "Quit"),
            self.lang.get("MenuTestMode", "Test Mode"),
        ]
        self.selected_index = 0
        self.profile_rect = None

    @staticmethod
    def _load_image(path, *, alpha, fallback=None):
        if not os.path.exists(path):
            print("WARNING: Main menu asset not found:", path)
            return fallback
        image = pygame.image.load(path)
        return image.convert_alpha() if alpha else image.convert()

    def _get_layout(self):
        viewport_size = self.screen.get_size()
        if self._layout is None or self._layout.viewport_size != viewport_size:
            title_size = self.title_image.get_size() if self.title_image else (3, 1)
            menu_size = self.menu_image.get_size() if self.menu_image else (16, 9)
            self._layout = build_start_page_layout(viewport_size, title_size, menu_size)
        return self._layout

    def _get_font(self, size):
        font = self._font_cache.get(size)
        if font is None:
            font = pygame.font.Font(self.font_path, size)
            self._font_cache[size] = font
        return font

    def _get_fitted_font(self, text, preferred_size, max_width):
        """Keep unusually long localized labels inside their frame section."""
        size = preferred_size
        font = self._get_font(size)
        while (
            size > 18
            and font.size(str(text))[0] * MENU_TEXT_SCALE_X > max_width
        ):
            size -= 1
            font = self._get_font(size)
        return font

    def _scaled(self, image, target_size):
        if image is None:
            return None
        key = (id(image), tuple(target_size))
        scaled = self._scaled_image_cache.get(key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(image, target_size)
            # Resizing needs only the latest size of each source image. Keeping
            # every intermediate window size retains large background surfaces.
            for old_key in tuple(self._scaled_image_cache):
                if old_key[0] == key[0]:
                    del self._scaled_image_cache[old_key]
            self._scaled_image_cache[key] = scaled
        return scaled

    def _render_text_cached(self, font, text, color, scale=1.0):
        cache_key = (id(font), str(text), tuple(color), scale)
        surface = self._text_surface_cache.get(cache_key)
        if surface is None:
            surface = font.render(str(text), True, color)
            scaled_width = max(1, round(surface.get_width() * MENU_TEXT_SCALE_X * scale))
            surface = pygame.transform.smoothscale(
                surface, (scaled_width, max(1, round(surface.get_height() * scale)))
            )
            # Solid ink matches the ribbon; transparency made the menu look faded.
            surface.set_alpha(MENU_TEXT_OPACITY)
            self._text_surface_cache[cache_key] = surface
        return surface

    def _draw_metal_text(self, font, label, center, highlighted, pressed):
        text = self._render_text_cached(
            font, label, PAPER_COLOR, MENU_HOVER_SCALE if highlighted else 1.0
        )
        rect = text.get_rect(center=center).move(2 if pressed else 0, 2 if pressed else 0)
        self.screen.blit(text, rect)
        if not highlighted and not pressed:
            return
        key = (id(font), str(label), pressed, text.get_size())
        if key not in self._bevel_cache:
            edges = []
            # Alpha differences keep the one-pixel bevel INSIDE the glyphs.
            for offset, color in (((1, 1), (171, 149, 115)), ((-1, -1), (42, 35, 28))):
                edge = text.copy()
                edge.set_alpha(255)
                shifted = pygame.Surface(edge.get_size(), pygame.SRCALPHA)
                shifted.blit(edge, offset)
                edge.blit(shifted, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
                edge.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
                edge.fill(color, special_flags=pygame.BLEND_RGB_ADD)
                edge.set_alpha(45 if pressed else 65)
                edges.append(edge)
            self._bevel_cache[key] = edges
        for edge in self._bevel_cache[key]:
            self.screen.blit(edge, rect)

    def _begin_press(self, target, action):
        if self._pending_action is None:
            self._pressed_target = target
            self._pending_action = action
            self._press_until = pygame.time.get_ticks() + PRESS_DURATION_MS
            self._play_button_sound()

    def _draw_cover_background(self):
        if self.master_background is None:
            self.screen.fill(BLACK)
            return
        target_size, position = cover_geometry(
            self.master_background.get_size(), self.screen.get_size()
        )
        self.screen.blit(self._scaled(self.master_background, target_size), position)

    def _get_menu_rect(self, index):
        layout = self._get_layout()
        font = self._get_font(layout.font_size)
        text = self._render_text_cached(font, self.menu_items[index], PAPER_COLOR)
        text_rect = text.get_rect(center=layout.row_centers[index + 1])
        padding_x = round(layout.menu_rect.width * 0.035)
        padding_y = round(layout.menu_rect.height * 0.012)
        return text_rect.inflate(padding_x * 2, padding_y * 2)

    def _get_profile_label(self):
        profile_word = self.lang.get("Profile", "Profile")
        return f"{profile_word}: {self.profile_name}" if self.profile_name else profile_word

    def _play_button_sound(self):
        sound = getattr(self, "button_sound", None)
        if sound:
            sound.play()

    def _activate_menu_item(self, index):
        self._play_button_sound()
        return ("start", "options", "quit", "test_mode")[index]

    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.VIDEORESIZE:
                # Pygame 2 resizes a RESIZABLE display surface automatically.
                # Re-read it so the next frame uses the real viewport.
                display_surface = pygame.display.get_surface()
                if display_surface is not None:
                    self.screen = display_surface
                self._layout = None

            if self._pending_action is not None:
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self._keyboard_focus = True
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif event.key == pygame.K_DOWN:
                    self._keyboard_focus = True
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._keyboard_focus = True
                    self._begin_press(self.selected_index, ("start", "options", "quit", "test_mode")[self.selected_index])

            if event.type == pygame.MOUSEMOTION:
                self._keyboard_focus = False
                mouse_pos = event.pos
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    continue
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        self.selected_index = index
                        break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    self._begin_press("profile", "profile")
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        self._begin_press(index, ("start", "options", "quit", "test_mode")[index])

        if self._pending_action is not None and pygame.time.get_ticks() >= self._press_until:
            action = self._pending_action
            self._pending_action = None
            self._pressed_target = None
            return action
        return None

    def _draw_composed_page(self, target_surface):
        previous_screen = self.screen
        previous_layout = self._layout
        self.screen = target_surface
        if previous_screen.get_size() != target_surface.get_size():
            self._layout = None

        layout = self._get_layout()
        self._draw_cover_background()

        menu_image = self._scaled(self.menu_image, layout.menu_image_rect.size)
        if menu_image is not None:
            self.screen.blit(menu_image, layout.menu_image_rect)

        title = self._scaled(self.title_image, layout.title_rect.size)
        if title is not None:
            self.screen.blit(title, layout.title_rect)

        font = self._get_font(layout.font_size)
        profile_label = self._get_profile_label()
        profile_font = self._get_fitted_font(
            profile_label, layout.font_size, round(layout.menu_rect.width * 0.82)
        )
        profile_center = layout.row_centers[0]
        profile_hover = self.profile_rect and self.profile_rect.collidepoint(pygame.mouse.get_pos())
        profile_color = LIGHT_GOLD if profile_hover else PAPER_COLOR
        profile_text = self._render_text_cached(profile_font, profile_label, profile_color)
        profile_text_rect = profile_text.get_rect(center=profile_center)
        self.profile_rect = profile_text_rect.inflate(
            round(layout.menu_rect.width * 0.07), round(layout.menu_rect.height * 0.024)
        )
        self._draw_metal_text(profile_font, profile_label, profile_center, profile_hover, self._pressed_target == "profile")

        for index, item in enumerate(self.menu_items):
            center_x, center_y = layout.row_centers[index + 1]
            highlighted = (self._keyboard_focus and index == self.selected_index) or self._get_menu_rect(index).collidepoint(pygame.mouse.get_pos())
            self._draw_metal_text(font, item, (center_x, center_y), highlighted, self._pressed_target == index)

        self.screen = previous_screen
        if previous_screen.get_size() == target_surface.get_size():
            self._layout = layout
        else:
            self._layout = previous_layout

    def draw(self):
        self._draw_composed_page(self.screen)

        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()
            if result in {"quit", "start", "profile", "options", "test_mode"}:
                return result
            self.draw()
            self.clock.tick(FPS)
