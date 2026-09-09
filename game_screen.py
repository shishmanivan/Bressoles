import os
import random
import sys

import pygame

from asset_loaders import load_scaled_image
from adaptive_ui import cover_geometry
from level_screen_helpers import (
    LEVEL_CONTENT_SIZE,
    LEVEL_BUTTON_ANCHOR_WIDTH,
    compute_arrow_position,
    level_content_rect,
    build_normal_mode_layout,
    build_test_mode_layout,
    compute_picture_position,
    load_primary_level_assets,
    load_test_level_pictures,
)
from level_card_style import LevelCardStyle
from level_routes import get_test_content_level
from shared_utils import wrap_text
from sound_assets import load_sound


SCREEN_WIDTH, SCREEN_HEIGHT = LEVEL_CONTENT_SIZE
MASTER_BACKGROUND_PATH = os.path.join("LevelPage", "Levels_master_background.png")
FPS = 60
PAGE_ARROW_FRAME_MS = 80
PAGE_ARROW_SIZE = (150, 100)
LEVEL_BUTTON_PRESS_MS = 500
LEVEL_BUTTON_PRESSED_SCALE = 0.88

BLACK = (0, 0, 0)
PAPER_COLOR = (32, 26, 20)


class GameScreen:
    def __init__(self, screen, background, font_path, test_mode=False, lang_dict=None, progress_flags=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.test_mode = test_mode
        self.lang = lang_dict or {}
        self.progress_flags = progress_flags or {}
        self.button_sound = load_sound(os.path.join("Sounds", "Level Button.wav"))
        self.page_arrow_sound = load_sound(os.path.join("Sounds", "Skrip.wav"))

        # Keep the master at its native aspect ratio; cover is applied to the
        # actual viewport, independently of the card composition.
        self.background = background
        if os.path.exists(MASTER_BACKGROUND_PATH):
            self.background = pygame.image.load(MASTER_BACKGROUND_PATH).convert()
        else:
            print("WARNING: Level master background not found:", MASTER_BACKGROUND_PATH)
        self._background_viewport_size = None
        self._viewport_background = None
        self._content_surface = pygame.Surface(LEVEL_CONTENT_SIZE, pygame.SRCALPHA)
        self._card_angles = {level: random.Random(7301 + level).choice((-4, -3, -2, 2, 3, 4))
                             for level in range(1, 14)}

        levelcard_path = os.path.join("LevelPage", "LevelCard.jpg")
        self.levelcard_image = load_scaled_image(
            levelcard_path,
            scale_factor=0.8,
            warning_message="WARNING: LevelCard.jpg not found:",
        )

        self.level_styles = {
            level: LevelCardStyle(self.levelcard_image.get_size(), level_num=level)
            for level in range(1, 7)
        } if self.levelcard_image else {}

        self.stamp_image = None
        self._rotated_stamps = {}
        if self.levelcard_image:
            # A circular stamp covering roughly one eighth of the card's area.
            card_area = self.levelcard_image.get_width() * self.levelcard_image.get_height()
            stamp_size = max(1, round((card_area / 8) ** 0.5))
            self.stamp_image = load_scaled_image(
                os.path.join("LevelPage", "Stamp.png"),
                target_size=(stamp_size, stamp_size),
                warning_message="WARNING: Stamp.png not found:",
            )

        padding_x = 40
        padding_y = 75
        self.card_position = (padding_x, padding_y)

        self.font_card = pygame.font.Font(font_path, 48)
        self.font_card_desc = pygame.font.Font(font_path, 32)
        self._description_fonts = {32: self.font_card_desc}
        self._font_path = font_path
        self._text_surface_cache = {}
        self._wrapped_text_cache = {}

        startarrow_path = os.path.join("LevelPage", "Level Button.png")
        self.startarrow_image = load_scaled_image(
            startarrow_path,
            warning_message="WARNING: Level Button.png not found:",
        )
        if self.startarrow_image is not None:
            # Trim the transparent canvas so the visible frame fits the small
            # gap after the card's bottom rule. Preserve the artwork's ratio.
            artwork = self.startarrow_image.subsurface(self.startarrow_image.get_bounding_rect())
            width = round(LEVEL_BUTTON_ANCHOR_WIDTH * 1.05 * 1.20)
            height = round(width * artwork.get_height() / artwork.get_width())
            self.startarrow_image = pygame.transform.smoothscale(artwork, (width, height))
        self._pending_level = None
        self._level_press_started_at = None
        self._level_press_drawn = False

        if self.levelcard_image and self.startarrow_image:
            card_width = self.levelcard_image.get_width()
            card_height = self.levelcard_image.get_height()
            arrow_width = self.startarrow_image.get_width()
            arrow_height = self.startarrow_image.get_height()
            arrow_padding = 15
            self.arrow_position = compute_arrow_position(
                self.card_position, (card_width, card_height),
                (arrow_width, arrow_height), padding=arrow_padding,
            )
            self.arrow_rect = pygame.Rect(self.arrow_position[0], self.arrow_position[1], arrow_width, arrow_height)
        else:
            self.arrow_position = (0, 0)
            self.arrow_rect = None

        self.card2_position = None
        self.arrow2_rect = None
        self.arrow2_position = (0, 0)
        self.card3_position = None
        self.arrow3_rect = None
        self.arrow3_position = (0, 0)
        self.card4_position = None
        self.arrow4_rect = None
        self.arrow4_position = (0, 0)
        self.card5_position = None
        self.arrow5_rect = None
        self.arrow5_position = (0, 0)
        self.card6_position = None
        self.arrow6_rect = None
        self.arrow6_position = (0, 0)

        primary_assets = load_primary_level_assets()
        self.level1_picture = primary_assets["level1_picture"]
        self.level2_picture = primary_assets["level2_picture"]
        self.level3_picture = primary_assets["level3_picture"]
        self.level4_picture = primary_assets["level4_picture"]
        self.level5_picture = primary_assets["level5_picture"]
        self.level6_picture = primary_assets["level6_picture"]
        self.level_pictures = load_test_level_pictures(13)
        for level_num, picture in enumerate(
            (
                self.level1_picture,
                self.level2_picture,
                self.level3_picture,
                self.level4_picture,
                self.level5_picture,
                self.level6_picture,
            ),
            start=1,
        ):
            self.level_pictures[level_num - 1] = picture
        self.level_pictures[12] = self.level6_picture

        self.scroll_y = 0
        self.max_scroll_y = 0
        self.card1_rect = None
        self.level_page_index = 0
        self.page_arrow_frames = [
            load_scaled_image(os.path.join("UI", "Arrow", f"Arrow_{frame}.png"),
                              target_size=PAGE_ARROW_SIZE)
            for frame in range(1, 5)
        ]
        self.page_arrow_back_frames = [
            pygame.transform.flip(frame, True, False) if frame is not None else None
            for frame in self.page_arrow_frames
        ]
        self.previous_page_rect = pygame.Rect(20, SCREEN_HEIGHT // 2 - 50, *PAGE_ARROW_SIZE)
        self.next_page_rect = pygame.Rect(SCREEN_WIDTH - 170, SCREEN_HEIGHT // 2 - 50, *PAGE_ARROW_SIZE)
        self._page_animation_started_at = None
        self._page_animation_fourth_at = None
        self._page_animation_frame = 0

        if self.test_mode:
            test_layout = build_test_mode_layout(
                self.levelcard_image,
                self.startarrow_image,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                padding_y,
            )
            self.num_levels = test_layout["num_levels"]
            self.cards_per_row = test_layout["cards_per_row"]
            self.cards_per_col = test_layout["cards_per_col"]
            self.test_card_positions = test_layout["test_card_positions"]
            self.test_card_rects = test_layout["test_card_rects"]
            self.max_scroll_y = test_layout["max_scroll_y"]
            self.test_level_pictures = load_test_level_pictures(self.num_levels)
        else:
            normal_layout = build_normal_mode_layout(
                self.levelcard_image,
                self.startarrow_image,
                SCREEN_WIDTH,
                padding_y,
            )
            self.card_position = normal_layout["card_position"]
            self.card2_position = normal_layout["card2_position"]
            self.card3_position = normal_layout["card3_position"]
            self.card4_position = normal_layout["card4_position"]
            self.card5_position = normal_layout["card5_position"]
            self.card6_position = normal_layout["card6_position"]
            self.arrow_position = normal_layout["arrow_position"]
            self.arrow2_position = normal_layout["arrow2_position"]
            self.arrow3_position = normal_layout["arrow3_position"]
            self.arrow4_position = normal_layout["arrow4_position"]
            self.arrow5_position = normal_layout["arrow5_position"]
            self.arrow6_position = normal_layout["arrow6_position"]
            self.arrow_rect = normal_layout["arrow_rect"]
            self.arrow2_rect = normal_layout["arrow2_rect"]
            self.arrow3_rect = normal_layout["arrow3_rect"]
            self.arrow4_rect = normal_layout["arrow4_rect"]
            self.arrow5_rect = normal_layout["arrow5_rect"]
            self.arrow6_rect = normal_layout["arrow6_rect"]
            self.card1_rect = normal_layout["card1_rect"]
            self.max_scroll_y = normal_layout["max_scroll_y"]
            self.normal_card_positions = [
                self.card_position,
                self.card2_position,
                self.card3_position,
                self.card4_position,
                self.card5_position,
                self.card6_position,
            ]
            self.normal_arrow_rects = [
                self.arrow_rect,
                self.arrow2_rect,
                self.arrow3_rect,
                self.arrow4_rect,
                self.arrow5_rect,
                self.arrow6_rect,
            ]

        for level_num, style in self.level_styles.items():
            index = level_num - 1
            if style is None or self.startarrow_image is None:
                continue
            # Each template shares its button geometry with hit testing.
            position = self.test_card_positions[index] if self.test_mode else self.normal_card_positions[index]
            rect = style.button_rect(position, self.startarrow_image.get_size())
            if self.test_mode:
                self.test_card_rects[index] = rect
            else:
                suffix = "" if index == 0 else str(index + 1)
                setattr(self, f"arrow{suffix}_rect", rect)
                setattr(self, f"arrow{suffix}_position", rect.topleft)
                self.normal_arrow_rects[index] = rect

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang.get(key, default)

    def _is_unlocked(self, level_key):
        return bool(self.progress_flags.get(level_key))

    def _is_completed(self, level_num):
        return self._is_unlocked(f"level_{level_num}_boss_defeated")

    def _is_level_unlocked(self, level_num):
        if self.test_mode:
            return True
        return {
            1: True,
            2: self._is_unlocked("level_1_boss_defeated"),
            3: self._is_unlocked("level_2_boss_defeated"),
            4: self._is_unlocked("level_3_boss_defeated"),
            5: self._is_unlocked("level_3_boss_defeated"),
            8: self._is_unlocked("level_8_unlocked"),
        }.get(int(level_num or 0), False)

    def _can_open_next_page(self):
        return any(self._is_level_unlocked(level_num) for level_num in range(7, 13))

    def _start_level(self, level_num):
        if getattr(self, "_pending_level", None) is not None:
            return None
        sound = getattr(self, "button_sound", None)
        if sound:
            sound.play()
        self._pending_level = level_num
        self._level_press_started_at = pygame.time.get_ticks()
        self._level_press_drawn = False
        return None

    def _render_text_cached(self, font, text, color):
        cache_key = (id(font), str(text), tuple(color))
        surface = self._text_surface_cache.get(cache_key)
        if surface is None:
            surface = font.render(str(text), True, color)
            self._text_surface_cache[cache_key] = surface
        return surface

    def _wrap_text_cached(self, text, font, max_width):
        cache_key = (id(font), text, max_width)
        lines = self._wrapped_text_cache.get(cache_key)
        if lines is None:
            lines = wrap_text(text, font, max_width)
            self._wrapped_text_cache[cache_key] = lines
        return lines

    def _draw_completed_stamp(self, card_position, level_num):
        if not self.stamp_image or not self._is_completed(level_num):
            return

        rotated_stamp = self._rotated_stamps.get(level_num)
        if rotated_stamp is None:
            rng = random.Random(0x5A17 + level_num * 7919)
            angle = rng.choice((-27, -22, -17, -12, 11, 16, 21, 26))
            rotated_stamp = pygame.transform.rotozoom(self.stamp_image, angle, 1.0)
            self._rotated_stamps[level_num] = rotated_stamp

        # Keep the apparently hand-stamped placement stable between frames and
        # visits, while giving every level its own position and tilt.
        rng = random.Random(0xC0DE + level_num * 3571)
        margin = 12
        max_x = max(margin, self.levelcard_image.get_width() - rotated_stamp.get_width() - margin)
        max_y = max(margin, self.levelcard_image.get_height() - rotated_stamp.get_height() - margin)
        offset_x = rng.randint(margin, max_x)
        offset_y = rng.randint(margin, max_y)
        self.screen.blit(rotated_stamp, (card_position[0] + offset_x, card_position[1] + offset_y))

    def _viewport_to_content(self, position):
        """Use the same transform for hit testing as for drawing the UI layer."""
        if not hasattr(self, "screen"):
            return position
        rect = level_content_rect(self.screen.get_size())
        if not rect.collidepoint(position):
            return None
        return (
            (position[0] - rect.x) * SCREEN_WIDTH / rect.width,
            (position[1] - rect.y) * SCREEN_HEIGHT / rect.height,
        )

    def _card_center(self, level_num):
        if self.test_mode:
            position = self.test_card_positions[level_num - 1]
        else:
            position = self.normal_card_positions[(level_num - 1) % 6]
        return pygame.Vector2(position[0] + self.levelcard_image.get_width() / 2,
                              position[1] + self.levelcard_image.get_height() / 2 - self.scroll_y)

    def _card_point_to_content(self, point, level_num):
        """Map an unrotated, scrolled card point to its visible position."""
        angle = getattr(self, "_card_angles", {}).get(level_num, 0)
        if not angle:
            return point
        center = self._card_center(level_num)
        return center + (pygame.Vector2(point) - center).rotate(-angle)

    def _level_button_hit(self, rect, point, level_num):
        if rect is None:
            return False
        angle = getattr(self, "_card_angles", {}).get(level_num, 0)
        if angle:
            center = self._card_center(level_num)
            point = center + (pygame.Vector2(point) - center).rotate(angle)
        return rect.move(0, -self.scroll_y).collidepoint(point)

    def handle_input(self):

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.VIDEORESIZE:
                display_surface = pygame.display.get_surface()
                if display_surface is not None:
                    self.screen = display_surface
                continue

            if getattr(self, "_pending_level", None) is not None:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._pending_level = None
                    self._level_press_drawn = False
                    return "back"
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
                if event.key == pygame.K_UP:
                    self.scroll_y = max(0, self.scroll_y - 50)
                elif event.key == pygame.K_DOWN:
                    self.scroll_y = min(self.max_scroll_y, self.scroll_y + 50)

            if event.type == pygame.MOUSEWHEEL:
                scroll_amount = event.y * 30
                self.scroll_y = max(0, min(self.max_scroll_y, self.scroll_y - scroll_amount))

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if getattr(self, "_page_animation_started_at", None) is not None:
                    continue
                mouse_pos = self._viewport_to_content(
                    getattr(event, "pos", pygame.mouse.get_pos())
                )
                if mouse_pos is None:
                    continue
                if self.test_mode:
                    for level_num in range(1, self.num_levels + 1):
                        card_index = level_num - 1
                        if card_index < len(self.test_card_rects) and self.test_card_rects[card_index]:
                            rect = self.test_card_rects[card_index]
                            if self._level_button_hit(rect, mouse_pos, level_num):
                                return self._start_level(level_num)
                else:
                    next_page_rect = getattr(self, "next_page_rect", None)
                    previous_page_rect = getattr(self, "previous_page_rect", None)
                    if (
                        getattr(self, "level_page_index", 0) == 0
                        and self._can_open_next_page()
                        and next_page_rect
                        and next_page_rect.collidepoint(mouse_pos)
                    ):
                        self._start_page_animation(1)
                        return None
                    if getattr(self, "level_page_index", 0) == 1 and previous_page_rect and previous_page_rect.collidepoint(mouse_pos):
                        self._start_page_animation(0)
                        return None

                    if getattr(self, "level_page_index", 0) == 0:
                        arrow_rects = getattr(self, "normal_arrow_rects", [
                            getattr(self, f"arrow{level_num if level_num > 1 else ''}_rect", None)
                            for level_num in range(1, 7)
                        ])
                        for level_num, rect in enumerate(arrow_rects, start=1):
                            if self._is_level_unlocked(level_num) and not self._is_completed(level_num) and self._level_button_hit(rect, mouse_pos, level_num):
                                return self._start_level(level_num)
                    else:
                        for offset, rect in enumerate(self.normal_arrow_rects):
                            level_num = 7 + offset
                            if self._is_level_unlocked(level_num) and not self._is_completed(level_num) and self._level_button_hit(rect, mouse_pos, level_num):
                                return self._start_level(level_num)

        if getattr(self, "_level_press_drawn", False):
            level_num = self._pending_level
            self._pending_level = None
            self._level_press_drawn = False
            return f"level_{level_num}"
        return None

    def _draw_level_card(self, card_position, level_num, level_picture, show_start_arrow=True):
        angle = getattr(self, "_card_angles", {}).get(level_num, 0)
        if not angle or not self.levelcard_image:
            return self._draw_level_card_flat(card_position, level_num, level_picture, show_start_arrow)
        # Rotate the whole clipping, including print, stamp and button.
        # Padding preserves the paper shadow and stamps past the paper edge.
        padding = 32
        size = self.levelcard_image.get_size()
        layer = pygame.Surface((size[0] + 2 * padding, size[1] + 2 * padding), pygame.SRCALPHA)
        target = self.screen
        self.screen = layer
        try:
            self._draw_level_card_flat((padding, padding), level_num, level_picture, show_start_arrow)
        finally:
            self.screen = target
        rotated = pygame.transform.rotozoom(layer, angle, 1.0)
        center = (card_position[0] + size[0] // 2, card_position[1] + size[1] // 2)
        target.blit(rotated, rotated.get_rect(center=center))

    def _draw_level_card_flat(self, card_position, level_num, level_picture, show_start_arrow=True):
        if not self.levelcard_image:
            return

        card_width = self.levelcard_image.get_width()
        card_height = self.levelcard_image.get_height()
        style = getattr(self, "level_styles", {}).get(level_num)
        if style is not None:
            style.draw(self.screen, card_position, level_picture,
                       self._get_text(f"Level{level_num}Year", {1: "1815", 2: "1825", 3: "1830", 4: "1845", 5: "1847", 6: "1850"}[level_num]),
                       self._get_text(f"Level{level_num}Cond", ""))
        else:
            self._draw_standard_card_content(card_position, level_num, level_picture, show_start_arrow)

        self._draw_completed_stamp(card_position, level_num)

        if show_start_arrow and self.startarrow_image:
            arrow_x, arrow_y = compute_arrow_position(
                card_position, (card_width, card_height), self.startarrow_image.get_size()
            )
            button_image = self.startarrow_image
            button_rect = button_image.get_rect(topleft=(arrow_x, arrow_y))
            if style is not None:
                button_rect = style.button_rect(card_position, button_image.get_size())
                button_image = pygame.transform.smoothscale(button_image, button_rect.size)
            if getattr(self, "_pending_level", None) == level_num:
                progress = min(1.0, max(0.0, (pygame.time.get_ticks() - self._level_press_started_at) / LEVEL_BUTTON_PRESS_MS))
                eased = progress * progress * (3 - 2 * progress)
                # Recede into the card around a fixed center, rather than
                # moving down its surface. Shading reinforces the depth.
                scale = 1.0 - (1.0 - LEVEL_BUTTON_PRESSED_SCALE) * eased
                pressed_size = tuple(max(1, round(size * scale)) for size in button_image.get_size())
                button_image = pygame.transform.smoothscale(button_image, pressed_size)
                shade = round(255 * (1.0 - 0.2 * eased))
                button_image.fill((shade, shade, shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
                button_rect = button_image.get_rect(center=button_rect.center)
                # Return the route on the next input pass, after the final
                # pressed pose has actually been presented by draw().
                self._level_press_drawn = progress >= 1.0
            self.screen.blit(button_image, button_rect)

    def _draw_standard_card_content(self, card_position, level_num, level_picture, show_start_arrow):
        card_width = self.levelcard_image.get_width()
        card_height = self.levelcard_image.get_height()
        self.screen.blit(self.levelcard_image, card_position)

        if level_picture:
            self.screen.blit(level_picture, compute_picture_position(card_position, card_height, level_picture))

        content_level = (
            get_test_content_level(level_num)
            if getattr(self, "test_mode", False)
            else level_num
        )
        desc_key = f"Level{content_level}Cond"
        desc_text = self._get_text(desc_key, None)
        year_key = f"Level{content_level}Year"
        year_text = self._get_text(year_key, None)
        text_left = card_position[0] + 250
        text_width = card_width - 250 - 15
        text_y = card_position[1] + 8
        year_surface = None

        if level_num >= 7 and (not year_text or year_text == year_key):
            year_text = f"Уровень {level_num}"
        if year_text and year_text != year_key:
            year_surface = self._render_text_cached(self.font_card, year_text, PAPER_COLOR)
            self.screen.blit(year_surface, (text_left + (text_width - year_surface.get_width()) // 2, text_y))

        if desc_text and desc_text != desc_key:
            year_height = year_surface.get_height() if year_surface else 0
            start_y = text_y + year_height + 20
            bottom = card_position[1] + card_height - 50
            if show_start_arrow and self.startarrow_image:
                bottom = min(bottom, card_position[1] + card_height
                             - self.startarrow_image.get_height() - 20)
            available_height = bottom - start_y

            # Fit the full description inside the card, including space for
            # the start arrow. Cache each font and wrap for subsequent frames.
            for font_size in range(32, 0, -1):
                if font_size not in self._description_fonts:
                    self._description_fonts[font_size] = pygame.font.Font(self._font_path, font_size)
                font = self._description_fonts[font_size]
                lines = self._wrap_text_cached(desc_text, font, text_width)
                line_height = font.get_height() + 5
                if (len(lines) * line_height - 5 <= available_height
                        and all(font.size(line)[0] <= text_width for line in lines)):
                    break

            for i, line in enumerate(lines):
                line_surface = self._render_text_cached(font, line, PAPER_COLOR)
                self.screen.blit(line_surface, (text_left, start_y + i * line_height))

    def _draw_cards(self):
        """Draw only the UI layer in the original card coordinate system."""
        if self.test_mode and self.levelcard_image:
            for level_num in range(1, self.num_levels + 1):
                card_index = level_num - 1
                if card_index < len(self.test_card_positions):
                    card_x, card_y = self.test_card_positions[card_index]
                    adjusted_y = card_y - self.scroll_y
                    if -self.levelcard_image.get_height() <= adjusted_y <= SCREEN_HEIGHT:
                        card_position = (card_x, adjusted_y)
                        level_picture = self.test_level_pictures[card_index] if card_index < len(self.test_level_pictures) else None
                        self._draw_level_card(card_position, level_num, level_picture)
            return

        if getattr(self, "level_page_index", 0) == 0:
            cards = [
                (level_num, position, self.level_pictures[level_num - 1], self._is_level_unlocked(level_num), not self._is_completed(level_num))
                for level_num, position in enumerate(self.normal_card_positions, start=1)
            ]
        else:
            cards = []
            for offset, position in enumerate(self.normal_card_positions):
                level_num = 7 + offset
                picture = self.level_pictures[level_num - 1]
                unlocked = self._is_level_unlocked(level_num)
                startable = unlocked and not self._is_completed(level_num)
                cards.append((level_num, position, picture, unlocked, startable))
        for level_num, position, picture, unlocked, startable in cards:
            if not unlocked or position is None:
                continue
            adjusted_position = (position[0], position[1] - self.scroll_y)
            if self.levelcard_image and (
                adjusted_position[1] > SCREEN_HEIGHT
                or adjusted_position[1] + self.levelcard_image.get_height() < 0
            ):
                continue
            self._draw_level_card(
                adjusted_position,
                level_num,
                picture,
                show_start_arrow=startable,
            )
        self._draw_page_navigation()
        return

    def draw(self):
        self._update_page_animation()
        viewport = self.screen
        viewport_size = viewport.get_size()
        if self.background is not None:
            if self._background_viewport_size != viewport_size:
                size, self._background_position = cover_geometry(
                    self.background.get_size(), viewport_size
                )
                self._viewport_background = pygame.transform.smoothscale(self.background, size)
                self._background_viewport_size = viewport_size
            viewport.blit(self._viewport_background, self._background_position)
        else:
            viewport.fill(BLACK)

        self._content_surface.fill((0, 0, 0, 0))
        self.screen = self._content_surface
        try:
            self._draw_cards()
        finally:
            self.screen = viewport

        rect = level_content_rect(viewport_size)
        content = self._content_surface
        if rect.size != LEVEL_CONTENT_SIZE:
            content = pygame.transform.smoothscale(content, rect.size)
        viewport.blit(content, rect)
        pygame.display.flip()

    def _start_page_animation(self, target):
        sound = getattr(self, "page_arrow_sound", None)
        if sound is not None:
            sound.play()
        self._page_animation_source = self.level_page_index
        self._page_animation_target = target
        self._page_animation_started_at = pygame.time.get_ticks()
        self._page_animation_fourth_at = None
        self._page_animation_frame = 0

    def _update_page_animation(self, now=None):
        started = getattr(self, "_page_animation_started_at", None)
        if started is None:
            return
        if now is None:
            now = pygame.time.get_ticks()
        self._page_animation_frame = min(3, max(0, (now - started) // PAGE_ARROW_FRAME_MS))
        if self._page_animation_frame == 3:
            if self._page_animation_fourth_at is None:
                # Commit before drawing the cards, and keep frame 4 visible for
                # a full interval even if a slow render skipped earlier frames.
                self.level_page_index = self._page_animation_target
                self.scroll_y = 0
                self._page_animation_fourth_at = now
            elif now - self._page_animation_fourth_at >= PAGE_ARROW_FRAME_MS:
                self._page_animation_started_at = None
                self._page_animation_frame = 0

    def _draw_page_navigation(self):
        """Keep the pressed arrow on its original side through frame 4."""
        if self.test_mode:
            return
        active = self._page_animation_started_at is not None
        source = self._page_animation_source if active else self.level_page_index
        if source == 0 and not self._can_open_next_page():
            return
        rect = self.next_page_rect if source == 0 else self.previous_page_rect
        frames = self.page_arrow_frames if source == 0 else self.page_arrow_back_frames
        frame = frames[self._page_animation_frame if active else 0]
        if frame is not None:
            self.screen.blit(frame, rect)

    def run(self):
        while True:
            result = self.handle_input()

            if result == "quit":
                pygame.quit()
                sys.exit()

            if result == "back":
                return "back"

            if result and result.startswith("level_"):
                return result

            self.draw()
            self.clock.tick(FPS)
