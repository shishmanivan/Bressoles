import os
import random
import sys

import pygame

from asset_loaders import load_scaled_background, load_scaled_image
from level_screen_helpers import (
    build_normal_mode_layout,
    build_test_mode_layout,
    compute_picture_position,
    load_primary_level_assets,
    load_test_level_pictures,
)
from shared_utils import wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

BLACK = (0, 0, 0)
PAPER_COLOR = (83, 76, 70)


class GameScreen:
    def __init__(self, screen, background, font_path, test_mode=False, lang_dict=None, progress_flags=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.test_mode = test_mode
        self.lang = lang_dict or {}
        self.progress_flags = progress_flags or {}

        back3_path = os.path.join("UI", "Back3.png")
        self.background = load_scaled_background(
            back3_path,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            fallback_surface=background,
            warning_message="WARNING: Back3.png not found:",
        )

        levelcard_path = os.path.join("LevelPage", "LevelCard.jpg")
        self.levelcard_image = load_scaled_image(
            levelcard_path,
            scale_factor=0.8,
            warning_message="WARNING: LevelCard.jpg not found:",
        )

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
        self._text_surface_cache = {}
        self._wrapped_text_cache = {}

        startarrow_path = os.path.join("LevelPage", "StartArrow.jpg")
        self.startarrow_image = load_scaled_image(
            startarrow_path,
            scale_factor=0.5,
            warning_message="WARNING: StartArrow.jpg not found:",
        )

        if self.levelcard_image and self.startarrow_image:
            card_width = self.levelcard_image.get_width()
            card_height = self.levelcard_image.get_height()
            arrow_width = self.startarrow_image.get_width()
            arrow_height = self.startarrow_image.get_height()
            arrow_padding = 15
            self.arrow_position = (
                self.card_position[0] + card_width - arrow_width - arrow_padding,
                self.card_position[1] + card_height - arrow_height - arrow_padding,
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

        self.scroll_y = 0
        self.max_scroll_y = 0
        self.card1_rect = None

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

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang.get(key, default)

    def _is_unlocked(self, level_key):
        return bool(self.progress_flags.get(level_key))

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
        if not self.stamp_image or not self._is_unlocked(f"level_{level_num}_boss_defeated"):
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

    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

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
                if self.test_mode:
                    for level_num in range(1, self.num_levels + 1):
                        card_index = level_num - 1
                        if card_index < len(self.test_card_rects) and self.test_card_rects[card_index]:
                            rect = self.test_card_rects[card_index]
                            adjusted_rect = pygame.Rect(rect.x, rect.y - self.scroll_y, rect.width, rect.height)
                            if adjusted_rect.collidepoint(mouse_pos):
                                return f"level_{level_num}"
                else:
                    def arrow_hit(rect):
                        if rect is None:
                            return False
                        return rect.move(0, -self.scroll_y).collidepoint(mouse_pos)

                    if arrow_hit(self.arrow_rect):
                        return "level_1"
                    if self._is_unlocked("level_1_boss_defeated") and arrow_hit(self.arrow2_rect):
                        return "level_2"
                    if self._is_unlocked("level_2_boss_defeated") and arrow_hit(self.arrow3_rect):
                        return "level_3"
                    if self._is_unlocked("level_3_boss_defeated") and arrow_hit(self.arrow4_rect):
                        return "level_4"
                    if self._is_unlocked("level_3_boss_defeated") and arrow_hit(self.arrow5_rect):
                        return "level_5"
                    if self._is_unlocked("level_6_unlocked") and arrow_hit(self.arrow6_rect):
                        return "level_6"

        return None

    def _draw_level_card(self, card_position, level_num, level_picture, show_start_arrow=True):
        if not self.levelcard_image:
            return

        card_width = self.levelcard_image.get_width()
        card_height = self.levelcard_image.get_height()
        self.screen.blit(self.levelcard_image, card_position)

        if level_picture:
            self.screen.blit(level_picture, compute_picture_position(card_position, card_height, level_picture))

        desc_key = f"Level{level_num}Cond"
        desc_text = self._get_text(desc_key, None)
        year_key = f"Level{level_num}Year"
        year_text = self._get_text(year_key, None)
        text_x = card_position[0] + 390
        text_y = card_position[1] + 8
        year_surface = None

        if year_text and year_text != year_key:
            year_surface = self._render_text_cached(self.font_card, year_text, PAPER_COLOR)
            self.screen.blit(year_surface, (text_x, text_y))

        if desc_text and desc_text != desc_key:
            lines = self._wrap_text_cached(desc_text, self.font_card_desc, 400)
            line_height = self.font_card_desc.get_height() + 5
            year_height = year_surface.get_height() if year_surface else 0
            start_y = text_y + year_height + 20
            start_x = card_position[0] + 250

            for i, line in enumerate(lines):
                line_surface = self._render_text_cached(self.font_card_desc, line, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))

        self._draw_completed_stamp(card_position, level_num)

        if show_start_arrow and self.startarrow_image:
            arrow_x = card_position[0] + card_width - self.startarrow_image.get_width() - 15
            arrow_y = card_position[1] + card_height - self.startarrow_image.get_height() - 15
            self.screen.blit(self.startarrow_image, (arrow_x, arrow_y))

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

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
            pygame.display.flip()
            return

        cards = [
            (1, self.card_position, self.level1_picture, True, True),
            (2, self.card2_position, self.level2_picture, self._is_unlocked("level_1_boss_defeated"), True),
            (3, self.card3_position, self.level3_picture, self._is_unlocked("level_2_boss_defeated"), True),
            (4, self.card4_position, self.level4_picture, self._is_unlocked("level_3_boss_defeated"), True),
            (5, self.card5_position, self.level5_picture, self._is_unlocked("level_3_boss_defeated"), True),
            (6, self.card6_position, self.level6_picture, self._is_unlocked("level_6_unlocked"), True),
        ]
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
        pygame.display.flip()
        return

        if self.levelcard_image:
            self.screen.blit(self.levelcard_image, self.card_position)

            picture_to_draw = self.level1_picture

            if picture_to_draw:
                card_height = self.levelcard_image.get_height()
                self.screen.blit(picture_to_draw, compute_picture_position(self.card_position, card_height, picture_to_draw))

            card_text = "1815"
            text_surface = self._render_text_cached(self.font_card, card_text, PAPER_COLOR)
            text_x = self.card_position[0] + 390
            text_y = self.card_position[1] + 8
            self.screen.blit(text_surface, (text_x, text_y))

            desc_text = self._get_text("Level1Cond", "Level1Cond")
            lines = self._wrap_text_cached(desc_text, self.font_card_desc, 400)
            line_height = self.font_card_desc.get_height() + 5
            start_y = text_y + text_surface.get_height() + 20
            start_x = self.card_position[0] + 250
            for i, line in enumerate(lines):
                line_surface = self._render_text_cached(self.font_card_desc, line, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))

            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow_position)

        if self._is_unlocked("level_1_boss_defeated") and self.levelcard_image:
            self.screen.blit(self.levelcard_image, self.card2_position)
            if self.level2_picture:
                card_height = self.levelcard_image.get_height()
                self.screen.blit(self.level2_picture, compute_picture_position(self.card2_position, card_height, self.level2_picture))

            text_surface = self._render_text_cached(self.font_card, "1825", PAPER_COLOR)
            text_x = self.card2_position[0] + 390
            text_y = self.card2_position[1] + 8
            self.screen.blit(text_surface, (text_x, text_y))

            desc_text = self._get_text("Level2Cond", "Level2Cond")
            lines = self._wrap_text_cached(desc_text, self.font_card_desc, 400)
            line_height = self.font_card_desc.get_height() + 5
            start_y = text_y + text_surface.get_height() + 20
            start_x = self.card2_position[0] + 250
            for i, line in enumerate(lines):
                line_surface = self._render_text_cached(self.font_card_desc, line, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))

            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow2_position)

        if self._is_unlocked("level_2_boss_defeated") and self.levelcard_image and self.card3_position:
            self.screen.blit(self.levelcard_image, self.card3_position)
            if self.level3_picture:
                card_height = self.levelcard_image.get_height()
                self.screen.blit(self.level3_picture, compute_picture_position(self.card3_position, card_height, self.level3_picture))

            text_surface = self._render_text_cached(self.font_card, "1830", PAPER_COLOR)
            text_x = self.card3_position[0] + 390
            text_y = self.card3_position[1] + 8
            self.screen.blit(text_surface, (text_x, text_y))

            desc_text = self._get_text("Level3Cond", "Level3Cond")
            lines = self._wrap_text_cached(desc_text, self.font_card_desc, 400)
            line_height = self.font_card_desc.get_height() + 5
            start_y = text_y + text_surface.get_height() + 20
            start_x = self.card3_position[0] + 250
            for i, line in enumerate(lines):
                line_surface = self._render_text_cached(self.font_card_desc, line, PAPER_COLOR)
                self.screen.blit(line_surface, (start_x, start_y + i * line_height))

            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow3_position)

        if self._is_unlocked("level_3_boss_defeated") and self.levelcard_image and self.card4_position:
            self.screen.blit(self.levelcard_image, self.card4_position)
            if self.level4_picture:
                card_height = self.levelcard_image.get_height()
                self.screen.blit(self.level4_picture, compute_picture_position(self.card4_position, card_height, self.level4_picture))

            year_key = "Level4Year"
            year_text = self._get_text(year_key, None)
            card_text = year_text if year_text and year_text != year_key else "1845"
            text_surface = self._render_text_cached(self.font_card, card_text, PAPER_COLOR)
            text_x = self.card4_position[0] + 390
            text_y = self.card4_position[1] + 8
            self.screen.blit(text_surface, (text_x, text_y))

            desc_key = "Level4Cond"
            desc_text = self._get_text(desc_key, None)
            if desc_text and desc_text != desc_key:
                lines = self._wrap_text_cached(desc_text, self.font_card_desc, 400)
                line_height = self.font_card_desc.get_height() + 5
                start_y = text_y + text_surface.get_height() + 20
                start_x = self.card4_position[0] + 250
                for i, line in enumerate(lines):
                    line_surface = self._render_text_cached(self.font_card_desc, line, PAPER_COLOR)
                    self.screen.blit(line_surface, (start_x, start_y + i * line_height))

            if self.startarrow_image:
                self.screen.blit(self.startarrow_image, self.arrow4_position)

        pygame.display.flip()

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
