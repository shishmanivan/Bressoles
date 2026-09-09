import os
from dataclasses import dataclass

import pygame

from adaptive_ui import AnchoredElement, clamp, cover_geometry, proportional_size
from sound_assets import load_button_sound


FPS = 60
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 235, 150)
PAPER_COLOR = (83, 76, 70)

MASTER_BACKGROUND_PATH = os.path.join("UI", "Master Background.png")
TITLE_PATH = os.path.join("UI", "Bressoles Title.png")
MENU_FRAME_PATH = os.path.join("UI", "Menu2.png")
RIBBON_PATH = os.path.join("UI", "Ribbon.png")
MAIN_BACK_PATH = os.path.join("UI", "MainBack2.png")
# The supplied asset is intentionally referenced with its on-disk spelling.
BOTTOM_PATH = os.path.join("UI", "Botton.png")
TOP_PATH = os.path.join("UI", "Top.png")


@dataclass(frozen=True)
class StartPageLayout:
    """All main-menu geometry, calculated only from the current viewport."""

    viewport_size: tuple
    title_rect: pygame.Rect
    menu_rect: pygame.Rect
    top_rect: pygame.Rect
    bottom_rect: pygame.Rect
    main_back_rect: pygame.Rect
    ribbon_rect: pygame.Rect
    row_centers: tuple
    font_size: int


def build_start_page_layout(
    viewport_size,
    title_source_size,
    menu_source_size,
    ribbon_source_size=(3, 1),
    main_back_source_size=(1021, 843),
    bottom_source_size=(2159, 253),
    top_source_size=(1238, 425),
):
    """Build the viewport-anchored equivalent of CSS clamp-based layout rules."""
    viewport_width, viewport_height = viewport_size

    horizontal_margin = round(clamp(24, viewport_width * 0.04, 90))
    title_top = round(clamp(24, viewport_height * 0.05, 80))
    title_width = round(clamp(320, viewport_width * 0.36, 760))
    title_size = proportional_size(title_source_size, width=title_width)
    title_rect = AnchoredElement(
        "left", "top", x_margin=horizontal_margin, y_margin=title_top
    ).rect(title_size, viewport_size)

    # The frame is intentionally restrained: at the 1920x1080 reference size it
    # occupies about 47% of the viewport height instead of dominating the screen.
    menu_height = round(clamp(306, viewport_height * 0.4675, 544))
    # Keep the frame inside short viewports while retaining its proportions.
    menu_height = min(menu_height, max(1, viewport_height - 2 * min(24, viewport_height // 20)))
    menu_size = proportional_size(menu_source_size, height=menu_height)
    menu_rect = AnchoredElement(
        "right", "center", x_margin=horizontal_margin
    ).rect(menu_size, viewport_size)

    # The masthead belongs to the menu, not to the master background. Keep its
    # centre locked to the frame and overlap their decorative edges slightly.
    top_width = round(menu_rect.width * 1.42 * 0.85)
    top_size = proportional_size(top_source_size, width=top_width)
    top_rect = pygame.Rect((0, 0), top_size)
    top_rect.centerx = menu_rect.centerx
    top_rect.bottom = menu_rect.top + round(menu_rect.height * 0.04)

    bottom_width = min(round(clamp(640, viewport_width, 2159)), viewport_width)
    bottom_size = proportional_size(bottom_source_size, width=bottom_width)
    bottom_rect = AnchoredElement("center", "bottom").rect(
        bottom_size, viewport_size
    )

    # MainBack2 is the complete left-hand illustration from the old composed
    # page. Keep it close to full viewport height and let the ribbon conceal
    # its extracted lower edge.
    main_back_height = min(
        round(clamp(560, viewport_height * 0.95, 1200)), viewport_height
    )
    main_back_size = proportional_size(
        main_back_source_size, height=main_back_height
    )
    main_back_gap = round(clamp(12, viewport_width * 0.012, 28))
    max_main_back_width = max(1, menu_rect.left - main_back_gap)
    if main_back_size[0] > max_main_back_width:
        main_back_size = proportional_size(
            main_back_source_size, width=max_main_back_width
        )
    main_back_rect = AnchoredElement(
        "left",
        "top",
        y_margin=round(clamp(12, viewport_height * 0.02, 30)),
    ).rect(main_back_size, viewport_size)

    # In the original 16:9 composition the ribbon spans most of the lower
    # width and continues beyond the edge of the page. Anchor it to the
    # viewport rather than to the cover-scaled master background: widening the
    # window then reveals more scenery instead of moving or stretching it.
    ribbon_width = round(clamp(520, viewport_width * 0.60, 1300))
    ribbon_width = min(ribbon_width, viewport_width)
    ribbon_size = proportional_size(ribbon_source_size, width=ribbon_width)
    ribbon_x_offset = -round(clamp(36, viewport_width * 0.07, 180))
    ribbon_rect = AnchoredElement(
        "center",
        "bottom",
        x_margin=ribbon_x_offset,
        y_margin=-round(ribbon_size[1] * 0.18),
    ).rect(ribbon_size, viewport_size)

    # A width-constrained MainBack2 becomes shorter on narrower screens.
    # Lower it only when necessary so its cut edge always remains safely
    # behind the solid central bend of the ribbon.
    required_main_back_bottom = ribbon_rect.top + round(ribbon_rect.height * 0.55)
    if main_back_rect.bottom < required_main_back_bottom:
        main_back_rect.bottom = required_main_back_bottom

    # Menu2.png contains five visual rows. These ratios are relative to the frame,
    # never to the 3440x1440 master background.
    row_ratios = (0.145, 0.333, 0.516, 0.696, 0.877)
    row_centers = tuple(
        (menu_rect.centerx, menu_rect.top + round(menu_rect.height * ratio))
        for ratio in row_ratios
    )
    # Menu typography stays deliberately substantial even when the decorative
    # frame is compact. Long profile names are fitted separately at draw time.
    font_size = round(clamp(34, menu_rect.height * 0.09, 50))
    return StartPageLayout(
        viewport_size=tuple(viewport_size),
        title_rect=title_rect,
        menu_rect=menu_rect,
        top_rect=top_rect,
        bottom_rect=bottom_rect,
        main_back_rect=main_back_rect,
        ribbon_rect=ribbon_rect,
        row_centers=row_centers,
        font_size=font_size,
    )


class StartPage:
    def __init__(self, screen, background, font_path, lang_dict=None, profile_name=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang = lang_dict if lang_dict else {}
        self.profile_name = (profile_name or "").strip()
        self.font_path = font_path

        self.master_background = self._load_image(
            MASTER_BACKGROUND_PATH, alpha=False, fallback=background
        )
        self.title_image = self._load_image(TITLE_PATH, alpha=True)
        self.menu_frame_image = self._load_image(MENU_FRAME_PATH, alpha=True)
        self.ribbon_image = self._load_image(RIBBON_PATH, alpha=True)
        self.main_back_image = self._load_image(MAIN_BACK_PATH, alpha=True)
        self.bottom_image = self._load_image(BOTTOM_PATH, alpha=True)
        self.top_image = self._load_image(TOP_PATH, alpha=True)
        self.button_sound = load_button_sound()

        self._scaled_image_cache = {}
        self._font_cache = {}
        self._text_surface_cache = {}
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
            menu_size = self.menu_frame_image.get_size() if self.menu_frame_image else (3, 4)
            ribbon_size = self.ribbon_image.get_size() if self.ribbon_image else (3, 1)
            main_back_size = self.main_back_image.get_size() if self.main_back_image else (1021, 843)
            bottom_size = self.bottom_image.get_size() if self.bottom_image else (2159, 253)
            top_size = self.top_image.get_size() if self.top_image else (1238, 425)
            self._layout = build_start_page_layout(
                viewport_size,
                title_size,
                menu_size,
                ribbon_size,
                main_back_size,
                bottom_size,
                top_size,
            )
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
        while size > 18 and font.size(str(text))[0] > max_width:
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

    def _render_text_cached(self, font, text, color):
        cache_key = (id(font), str(text), tuple(color))
        surface = self._text_surface_cache.get(cache_key)
        if surface is None:
            surface = font.render(str(text), True, color)
            self._text_surface_cache[cache_key] = surface
        return surface

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

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return self._activate_menu_item(self.selected_index)

            if event.type == pygame.MOUSEMOTION:
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    continue
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        self.selected_index = index
                        break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    self._play_button_sound()
                    return "profile"
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        return self._activate_menu_item(index)

        return None

    def _draw_composed_page(self, target_surface):
        previous_screen = self.screen
        previous_layout = self._layout
        self.screen = target_surface
        if previous_screen.get_size() != target_surface.get_size():
            self._layout = None

        layout = self._get_layout()
        self._draw_cover_background()

        main_back = self._scaled(self.main_back_image, layout.main_back_rect.size)
        if main_back is not None:
            self.screen.blit(main_back, layout.main_back_rect)

        bottom = self._scaled(self.bottom_image, layout.bottom_rect.size)
        if bottom is not None:
            self.screen.blit(bottom, layout.bottom_rect)

        # Draw after the left illustration so the ribbon naturally masks its
        # lower edge instead of requiring a resolution-specific crop.
        ribbon = self._scaled(self.ribbon_image, layout.ribbon_rect.size)
        if ribbon is not None:
            self.screen.blit(ribbon, layout.ribbon_rect)

        title = self._scaled(self.title_image, layout.title_rect.size)
        if title is not None:
            self.screen.blit(title, layout.title_rect)

        menu_frame = self._scaled(self.menu_frame_image, layout.menu_rect.size)
        if menu_frame is not None:
            self.screen.blit(menu_frame, layout.menu_rect)

        top = self._scaled(self.top_image, layout.top_rect.size)
        if top is not None:
            self.screen.blit(top, layout.top_rect)

        font = self._get_font(layout.font_size)
        profile_label = self._get_profile_label()
        profile_font = self._get_fitted_font(
            profile_label, layout.font_size, round(layout.menu_rect.width * 0.82)
        )
        profile_center = layout.row_centers[0]
        profile_hover = self.profile_rect and self.profile_rect.collidepoint(pygame.mouse.get_pos())
        profile_color = LIGHT_GOLD if profile_hover else PAPER_COLOR
        profile_shadow = self._render_text_cached(profile_font, profile_label, BLACK)
        profile_text = self._render_text_cached(profile_font, profile_label, profile_color)
        shadow_offset = max(1, round(layout.font_size / 24))
        profile_shadow_rect = profile_shadow.get_rect(
            center=(profile_center[0] + shadow_offset, profile_center[1] + shadow_offset)
        )
        profile_text_rect = profile_text.get_rect(center=profile_center)
        self.profile_rect = profile_text_rect.inflate(
            round(layout.menu_rect.width * 0.07), round(layout.menu_rect.height * 0.024)
        )
        self.screen.blit(profile_shadow, profile_shadow_rect)
        self.screen.blit(profile_text, profile_text_rect)

        for index, item in enumerate(self.menu_items):
            center_x, center_y = layout.row_centers[index + 1]
            highlighted = index == self.selected_index
            color = LIGHT_GOLD if highlighted else PAPER_COLOR
            text = self._render_text_cached(font, item, color)
            text_rect = text.get_rect(center=(center_x, center_y))

            if highlighted:
                indicator = self._render_text_cached(font, ">", GOLD)
                indicator_gap = round(layout.menu_rect.width * 0.055)
                indicator_rect = indicator.get_rect(
                    midright=(text_rect.left - indicator_gap, center_y)
                )
                self.screen.blit(indicator, indicator_rect)

            shadow = self._render_text_cached(font, item, BLACK)
            shadow_rect = shadow.get_rect(
                center=(center_x + shadow_offset, center_y + shadow_offset)
            )
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(text, text_rect)

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
