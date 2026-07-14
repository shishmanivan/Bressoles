import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from asset_loaders import find_font_path_or_exit
from boss_page import POPUP_TEXT_BOTTOM_PADDING, build_boss_popup_text_layout
from game_data import load_language
from gameplay_winlose import build_win_result_layout
from round_page_helpers import build_completed_round_lines
from silver_black_page import SilverBlackPage


class UiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1680, 1050))
        cls.font_path = find_font_path_or_exit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_localized_boss_popup_text_fits_the_newspaper_card(self):
        popup_height = 375
        for language in ("RU", "ENG"):
            lang = load_language(language)
            for boss_number in range(1, 11):
                with self.subTest(language=language, boss=boss_number):
                    layout = build_boss_popup_text_layout(
                        self.font_path,
                        popup_height,
                        lang[f"Boss{boss_number}Text"],
                        lang["PopUpReward"],
                        lang[f"Boss{boss_number}Reward"],
                    )
                    self.assertGreaterEqual(layout["font_size"], 18)
                    self.assertLessEqual(
                        layout["content_bottom"],
                        popup_height - POPUP_TEXT_BOTTOM_PADDING,
                    )

    def test_lifecycle_labels_and_continue_button_do_not_overlap_cards(self):
        page = SilverBlackPage(
            self.screen,
            self.font_path,
            [201, 202],
            [301],
            [401],
            active_black_cards=[301],
            lang_dict=load_language("RU"),
        )

        rows = {
            "active": page.active_rects,
            "silver": page.silver_rects,
            "black": page.black_rects,
            "gold": page.gold_rects,
        }
        for kind, rects in rows.items():
            with self.subTest(kind=kind):
                label_rect = page.row_label_rects[kind]
                self.assertGreaterEqual(label_rect.left, page.panel_rect.left)
                self.assertLessEqual(label_rect.right, rects[0].left - 24)
                self.assertFalse(any(label_rect.colliderect(card_rect) for card_rect in rects))
        all_card_rects = [rect for rects in rows.values() for rect in rects]
        self.assertFalse(any(page.continue_button_rect.colliderect(rect) for rect in all_card_rects))
        self.assertTrue(page.panel_rect.contains(page.continue_button_rect))

    def test_lifecycle_continue_button_returns_the_current_selection(self):
        page = SilverBlackPage(
            self.screen,
            self.font_path,
            [201],
            [301],
            [401],
            active_black_cards=[301],
            lang_dict=load_language("RU"),
        )

        result = page._handle_mouse_down(page.continue_button_rect.center)

        self.assertEqual(result["active_black_cards"], [301])
        self.assertEqual(result["active_gold_cards"], [])

    def test_completed_round_lines_can_be_rebuilt_from_saved_choices(self):
        base_rects = {
            "e": pygame.Rect(350, 650, 100, 100),
            "m": pygame.Rect(350, 550, 100, 100),
            "h": pygame.Rect(350, 450, 100, 100),
        }

        lines = build_completed_round_lines(
            {1, 2, 3},
            {1: {"key": "m"}, 2: {"key": "e"}, 3: {"key": "h"}},
            base_rects,
            lambda round_num: (150 * (round_num - 1), -100 * (round_num - 1)),
            origin=(235, 832),
        )

        self.assertEqual(
            lines,
            [
                (235, 832, 400, 600),
                (400, 600, 550, 600),
                (550, 600, 700, 300),
            ],
        )

    def test_long_final_victory_content_stays_inside_result_window(self):
        lang = load_language("RU")
        window = pygame.Rect(560, 350, 560, 350)
        ok_button = pygame.Rect(1010, 628, 80, 42)

        layout = build_win_result_layout(
            self.font_path,
            [
                lang["RewardLevel4FinalBoss"],
                lang["BossVictoryDeckReset"],
                "Long принес прибыль: 5 наполеондоров",
            ],
            window,
            ok_button,
            card_count=2,
        )

        cards_rect = pygame.Rect(
            layout["card_start_x"],
            layout["card_y"],
            2 * layout["card_width"] + layout["card_gap"],
            layout["card_height"],
        )
        self.assertGreaterEqual(layout["card_y"], layout["text_bottom"] + 5)
        self.assertTrue(window.contains(cards_rect))
        self.assertFalse(cards_rect.colliderect(ok_button))


if __name__ == "__main__":
    unittest.main()
