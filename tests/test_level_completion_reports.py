"""Check the actual final-report path in every supported language."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import game_state
from asset_loaders import find_font_path_or_exit
from game_data import load_language
from gameplay_page import GameplayPage
from localization import SUPPORTED_LANGUAGES, get_language, set_language


class LevelCompletionReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()
        cls.font_path = find_font_path_or_exit()

    def make_page(self, language, level):
        page = GameplayPage.__new__(GameplayPage)
        page.lang_dict = load_language(language)
        page.level_number = level
        page.is_boss_fight = page.is_final_boss = True
        page.font_path = self.font_path
        # A restored generic message must not hide the level's unlocks.
        page.reward_window_text = page.lang_dict["RewardWindowText"]
        for number in range(1, 6):
            setattr(page, f"reward_level{number}_final_boss_text",
                    page.lang_dict[f"RewardLevel{number}FinalBoss"])
        page.last_earned_cards = (
            game_state.get_level_completion_reward_cards(level)
            + game_state.get_level_completion_black_reward_cards(level)
        )
        return page

    def setUp(self):
        # Check first-time rewards independently of other tests' puzzle progress.
        inventory = patch.object(game_state, "black_cards", [])
        inventory.start()
        self.addCleanup(inventory.stop)

    def test_final_reports_use_level_specific_text_and_include_awarded_cards(self):
        for language in SUPPORTED_LANGUAGES:
            for level, cards in {1: [15], 2: [13], 3: [110, 301], 4: [302], 5: [303, 304]}.items():
                with self.subTest(language=language, level=level):
                    page = self.make_page(language, level)
                    self.assertEqual(page._get_card_report_boss_description(),
                                     page.lang_dict[f"RewardLevel{level}FinalBoss"])
                    self.assertEqual([row["card_id"] for row in page._get_card_report_rows()], cards)

    def test_starting_currency_bonus_is_reported_in_every_language(self):
        for language in SUPPORTED_LANGUAGES:
            for level in range(2, 6):
                flags = {f"level_{number}_boss_defeated": number == level for number in range(1, 6)}
                with self.subTest(language=language, level=level), patch.multiple(game_state, **flags):
                    bonus = game_state.get_starting_napoleondors_for_level(level + 1)
                    self.assertGreater(bonus, 0)
                    self.assertIn(f" {bonus} ", self.make_page(language, level)._get_card_report_boss_description())

    def test_all_bonus_lines_fit_above_footer_in_every_language(self):
        previous_language = get_language()
        self.addCleanup(set_language, previous_language)
        # Reports use the game's 1680x1050 logical canvas.
        height = int(1050 * 0.84)
        rect = pygame.Rect(0, 0, int(height * 1086 / 1448), height)
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            for level in range(1, 6):
                with self.subTest(language=language, level=level):
                    page = self.make_page(language, level)
                    page.frugality_bonus_turns = 3
                    drawn = []

                    class Screen:
                        def blit(self, surface, position):
                            drawn.append(surface.get_rect(topleft=position))

                    page.screen = Screen()
                    count = len(page.last_earned_cards)
                    top = int(height * 0.325) + min(int(height * 0.36), count * int(height * 0.15))
                    page._draw_card_report_boss_text(rect, top + int(height * 0.018), int(rect.width * 0.29), count)
                    footer = drawn[-1]
                    self.assertGreater(len(drawn), 2)
                    for line in drawn[1:-1]:
                        self.assertLessEqual(line.bottom, footer.top - 12)
                        self.assertLessEqual(line.right, rect.right)


if __name__ == "__main__":
    unittest.main()
