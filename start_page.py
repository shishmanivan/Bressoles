import os
import math
import random
from dataclasses import dataclass

import pygame

from adaptive_ui import AnchoredElement, clamp, cover_geometry, proportional_size
from sound_assets import load_card_hover_sound, load_sound
from ribbon_letters import RibbonLetterHover


FPS = 60
BLACK = (0, 0, 0)
# Median dark ink sampled from the lettering on the ribbon beneath the sack.
PAPER_COLOR = (77, 63, 50)
LIGHT_GOLD = PAPER_COLOR
MENU_TEXT_OPACITY = 255
MENU_HOVER_SCALE = 1.02
PRESS_DURATION_MS = 90
# The custom display face has narrow proportions in its vector outlines.
MENU_TEXT_SCALE_X = 1.0

MASTER_BACKGROUND_PATH = os.path.join("UI", "Master Background.png")
TITLE_PATH = os.path.join("UI", "Bressoles Title.png")
MENU_IMAGE_PATH = os.path.join("UI", "Menu3_1.png")
MENU_FONT_PATH = os.path.join("Fonts", "BressolesDisplay-Regular.ttf")


@dataclass(frozen=True)
class SmokeSource:
    """Distances are pixels in Menu3's 1678 x 937 artwork; times are seconds.

    Opacity is 0..1; scale multiplies a 64 px smoke sprite. A short fade-in
    precedes start_opacity, then density falls toward end_opacity.
    """

    position: tuple
    spawn_interval: float = 0.48
    upward_speed: float = 14.0
    horizontal_drift: float = 3.8
    start_opacity: float = 0.60
    end_opacity: float = 0.0
    start_scale: float = 0.18
    end_scale: float = 1.05
    lifetime: float = 7.2
    phase: float = 0.0


# Add/remove entries to change the number of chimney emitters.
SMOKE_SOURCES = (
    SmokeSource((162, 660)),
    SmokeSource((276, 691), spawn_interval=0.65, upward_speed=12.0,
                horizontal_drift=3.0, start_opacity=0.48,
                end_scale=0.80, lifetime=5.8, phase=0.31),
)
SMOKE_COLOR = (225, 219, 204)
SMOKE_INTENSITY = 1.0
SMOKE_REFERENCE_SIZE = (1678, 937)
# Safety bounds around the chimneys, well clear of the menu and title.
SMOKE_REGION = (85, 510, 285, 190)

BEACON_CENTER = (115, 654)
BEACON_PERIOD = 4.8
BEACON_INTENSITY = 0.95
CALCULATOR_POSITION = (587, 674)
CALCULATOR_PAPER = (210, 184, 144)
CALCULATOR_INK = (67, 52, 37)
CALCULATOR_CHANGE_INTERVAL = 3.2
CALCULATOR_ROLL_SECONDS = 0.65
CALCULATOR_DIGITS = 6


def _calculator_number(step):
    """Stable random-looking drum positions, independent of rendering FPS."""
    rng = random.Random(8137 + step)
    return ''.join(str(rng.randrange(10)) for _ in range(CALCULATOR_DIGITS))


def _make_smoke_sprites():
    """Small reusable soft, irregular density textures; no extra PNG dependency."""
    sprites = []
    for variant in range(3):
        rng = random.Random(71 + variant)
        lobes = [(rng.uniform(-0.3, 0.3), rng.uniform(-0.35, 0.35),
                  rng.uniform(0.22, 0.42)) for _ in range(5)]
        sprite = pygame.Surface((64, 64), pygame.SRCALPHA)
        for y in range(64):
            for x in range(64):
                nx, ny = (x - 31.5) / 31.5, (y - 31.5) / 31.5
                density = sum(math.exp(-((nx - cx) ** 2 + (ny - cy) ** 2)
                                       / radius ** 2) for cx, cy, radius in lobes)
                edge = max(0.0, 1.0 - nx * nx - ny * ny)
                grain = 0.90 + 0.10 * math.sin(x * 0.63 + math.sin(y * 0.41))
                alpha = round(255 * min(1.0, density * 0.55) * edge * grain)
                sprite.set_at((x, y), (*SMOKE_COLOR, alpha))
        sprites.append(sprite)
    return tuple(sprites)


def _smoke_particles(source, seconds):
    """Analytic births keep emission frame-rate independent and memory bounded."""
    interval = max(0.05, source.spawn_interval)
    lifetime = max(0.1, source.lifetime)
    time = seconds + source.phase
    latest = math.floor(time / interval)
    oldest = math.floor((time - lifetime) / interval) + 1
    for index in range(oldest, latest + 1):
        age = time - index * interval
        progress = age / lifetime
        rng = random.Random(index + round(source.position[0] * 100))
        variation = rng.uniform(0.80, 1.20)
        bend = rng.uniform(-2.8, 2.8)
        x = (source.position[0] + source.horizontal_drift * age * variation
             + bend * math.sin(progress * math.pi * 2) * progress)
        y = source.position[1] - source.upward_speed * age * variation
        scale = source.start_scale + (source.end_scale - source.start_scale) * progress
        opacity = source.start_opacity + (source.end_opacity - source.start_opacity) * progress
        # Both ends are transparent, including when end_opacity is nonzero.
        fade_in = min(1.0, age / 0.35)
        fade_out = min(1.0, (lifetime - age) / 1.2)
        opacity *= fade_in * fade_in * (3 - 2 * fade_in)
        opacity *= fade_out * fade_out * (3 - 2 * fade_out)
        yield x, y, scale, clamp(0.0, opacity * SMOKE_INTENSITY, 1.0), index % 3


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
    # The reference's full capitals occupy about 9% of the frame's height.
    # Bressoles Display's cap height is 70% of its em size.
    font_size = round(clamp(28, menu_rect.height * 0.126, 88))
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
        self.hover_sound = load_card_hover_sound()

        self._scaled_image_cache = {}
        self._font_cache = {}
        self._text_surface_cache = {}
        self._bevel_cache = {}
        self._pending_action = None
        self._pressed_target = None
        self._keyboard_focus = False
        self._mouse_hovered_target = None
        self._layout = None
        self._smoke_sprites = _make_smoke_sprites()
        self._smoke_started_at = pygame.time.get_ticks()
        self._detail_started_at = None
        self._calculator_assets = None
        self._beacon_sprite = self._make_beacon_sprite()
        self._ribbon_letters = RibbonLetterHover(self.menu_image)

        self.menu_items = [
            self.lang.get("MenuStart", "Start Game"),
            self.lang.get("MenuOption", "Options"),
            self.lang.get("MenuQuit", "Quit"),
            self.lang.get("MenuLanguages", "Языки"),
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

    @staticmethod
    def _make_beacon_sprite():
        sprite = pygame.Surface((48, 48), pygame.SRCALPHA)
        for y in range(48):
            for x in range(48):
                radius = math.hypot(x - 23.5, y - 23.5)
                halo = max(0, 1 - radius / 23.5) ** 3 * 65
                core = math.exp(-(radius / 3.2) ** 2) * 225
                sprite.set_at((x, y), (255, 221, 151, min(255, round(halo + core))))
        return sprite

    def _draw_menu_details(self, layout):
        if self.menu_image is None:
            return
        now = pygame.time.get_ticks()
        if self._detail_started_at is None:
            self._detail_started_at = now
        seconds = (now - self._detail_started_at) / 1000.0
        art = layout.menu_image_rect
        sx, sy = art.width / 1678, art.height / 937
        # A soft pulse with a dark pause, never an abrupt on/off flash.
        pulse = max(0.0, math.sin(math.tau * seconds / BEACON_PERIOD)) ** 2
        glow = pygame.transform.smoothscale(self._beacon_sprite,
                  (max(1, round(24 * sx)), max(1, round(24 * sy))))
        glow.set_alpha(round(255 * clamp(0, pulse * BEACON_INTENSITY, 1)))
        self.screen.blit(glow, glow.get_rect(center=(art.left + round(BEACON_CENTER[0] * sx),
                                                    art.top + round(BEACON_CENTER[1] * sy))))

        # Build the inset at 3x resolution. It covers only the old inscription,
        # retaining the original metal frame and the panel's perspective.
        if self._calculator_assets is None:
            plate = pygame.Surface((222, 45))
            rng = random.Random(84)
            for y in range(45):
                for x in range(222):
                    shade = rng.randrange(-2, 3) - round(abs(y - 22) / 12)
                    plate.set_at((x, y), tuple(c + shade for c in CALCULATOR_PAPER))
            font = self._get_font(51)
            glyphs = []
            for digit in '0123456789':
                text = font.render(digit, True, CALCULATOR_INK)
                text = text.subsurface(text.get_bounding_rect()).copy()
                glyphs.append(pygame.transform.smoothscale(text, (20, 30)))
            self._calculator_assets = plate, glyphs
        plate, glyphs = self._calculator_assets
        panel = plate.copy()
        step = int(seconds / CALCULATOR_CHANGE_INTERVAL)
        phase = seconds % CALCULATOR_CHANGE_INTERVAL
        current = _calculator_number(step)
        following = _calculator_number(step + 1)
        for column, (old, new) in enumerate(zip(current, following)):
            # Short stagger between drums; outgoing numbers move UP while the
            # incoming row rises from BELOW, clipped by the physical window.
            start = CALCULATOR_CHANGE_INTERVAL - CALCULATOR_ROLL_SECONDS - 0.055 * (CALCULATOR_DIGITS - 1 - column)
            progress = clamp(0, (phase - start) / CALCULATOR_ROLL_SECONDS, 1)
            progress = progress * progress * (3 - 2 * progress)
            offset = round(progress * 45)
            x = 13 + column * 34
            panel.blit(glyphs[int(old)], (x, 7 - offset))
            panel.blit(glyphs[int(new)], (x, 52 - offset))
        skewed = pygame.Surface((243, 45), pygame.SRCALPHA)
        for row in range(45):
            skewed.blit(panel, (round(row * 21 / 44), row), (0, row, 222, 1))
        inset = pygame.transform.rotate(skewed, 3.14)
        inset = pygame.transform.smoothscale(inset, (max(1, round(inset.get_width() / 3 * sx)),
                                                     max(1, round(inset.get_height() / 3 * sy))))
        self.screen.blit(inset, (art.left + round(CALCULATOR_POSITION[0] * sx),
                                 art.top + round(CALCULATOR_POSITION[1] * sy)))

    def _draw_smoke(self, layout):
        if self.menu_image is None:
            return
        artwork = layout.menu_image_rect
        sx = artwork.width / SMOKE_REFERENCE_SIZE[0]
        sy = artwork.height / SMOKE_REFERENCE_SIZE[1]
        seconds = (pygame.time.get_ticks() - self._smoke_started_at) / 1000.0
        # Pre-roll a mature stream so the main menu is alive immediately.
        seconds += max((source.lifetime for source in SMOKE_SOURCES), default=0)
        x, y, width, height = SMOKE_REGION
        clip = pygame.Rect(artwork.left + round(x * sx), artwork.top + round(y * sy),
                           round(width * sx), round(height * sy))
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(previous_clip.clip(clip))
        try:
            for source in SMOKE_SOURCES:
                for px, py, scale, opacity, variant in _smoke_particles(source, seconds):
                    size = (max(1, round(64 * scale * sx)), max(1, round(64 * scale * sy)))
                    sprite = pygame.transform.smoothscale(self._smoke_sprites[variant], size)
                    sprite.set_alpha(round(255 * opacity))
                    center = (artwork.left + round(px * sx), artwork.top + round(py * sy))
                    self.screen.blit(sprite, sprite.get_rect(center=center))
        finally:
            self.screen.set_clip(previous_clip)

    def _get_profile_label(self):
        profile_word = self.lang.get("Profile", "Profile")
        return f"{profile_word}: {self.profile_name}" if self.profile_name else profile_word

    def _play_button_sound(self):
        sound = getattr(self, "button_sound", None)
        if sound:
            sound.play()

    def _play_hover_sound(self):
        sound = getattr(self, "hover_sound", None)
        if sound:
            sound.play()

    def _set_mouse_hover_target(self, target):
        previous = getattr(self, "_mouse_hovered_target", None)
        self._mouse_hovered_target = target
        if target is not None and target != previous:
            self._play_hover_sound()

    def _activate_menu_item(self, index):
        self._play_button_sound()
        return ("start", "options", "quit", "languages")[index]

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
                    self._mouse_hovered_target = None
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                    self._play_hover_sound()
                elif event.key == pygame.K_DOWN:
                    self._keyboard_focus = True
                    self._mouse_hovered_target = None
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                    self._play_hover_sound()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._keyboard_focus = True
                    self._begin_press(self.selected_index, ("start", "options", "quit", "languages")[self.selected_index])

            if event.type == pygame.MOUSEMOTION:
                self._keyboard_focus = False
                mouse_pos = event.pos
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    self._set_mouse_hover_target("profile")
                    continue
                hovered_index = None
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        self.selected_index = index
                        hovered_index = index
                        break
                self._set_mouse_hover_target(hovered_index)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                if self.profile_rect and self.profile_rect.collidepoint(mouse_pos):
                    self._begin_press("profile", "profile")
                for index in range(len(self.menu_items)):
                    if self._get_menu_rect(index).collidepoint(mouse_pos):
                        self._begin_press(index, ("start", "options", "quit", "languages")[index])

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

        self._draw_smoke(layout)
        self._draw_menu_details(layout)
        self._ribbon_letters.draw(self.screen, layout.menu_image_rect,
                                  pygame.mouse.get_pos(), pygame.time.get_ticks(),
                                  self._play_hover_sound)

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
            if result in {"quit", "start", "profile", "options", "languages"}:
                return result
            self.draw()
            self.clock.tick(FPS)
