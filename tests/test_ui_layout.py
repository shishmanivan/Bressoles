import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from asset_loaders import find_font_path_or_exit
from boss_page import (
    LEVEL5_BOSS_VERTICAL_SPACING,
    POPUP_TEXT_BOTTOM_PADDING,
    build_boss_popup_text_layout,
    build_next_boss_positions,
    get_boss_vertical_spacing,
    rebuild_boss_route_layout,
)
from game_data import load_language
from gameplay_winlose import build_win_result_layout
from round_page_helpers import build_completed_round_lines
from silver_black_page import ReplicationSilverPage, SilverBlackPage


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

    def test_replication_storage_shows_only_silver_slots_and_requires_selection(self):
        page = ReplicationSilverPage(
            self.screen,
            self.font_path,
            [201, 203],
            lang_dict=load_language("RU"),
        )

        self.assertEqual(len(page.silver_rects), 8)
        self.assertEqual(page.black_cards, [])
        self.assertEqual(page.gold_cards, [])
        self.assertIsNone(page._handle_mouse_down(page.confirm_button_rect.center))

        self.assertIsNone(page._handle_mouse_down(page.silver_rects[1].center))
        self.assertEqual(page.selected_index, 1)
        self.assertEqual(page._handle_mouse_down(page.confirm_button_rect.center), 203)

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

    def test_fourth_boss_choice_keeps_both_candidates_on_screen(self):
        positions = build_next_boss_positions(
            anchor_center=(800, 50),
            choice_count=2,
            vertical_spacing=150,
            screen_height=1050,
        )

        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0][0], positions[1][0])
        self.assertEqual(abs(positions[0][1] - positions[1][1]), 150)
        for _, center_y in positions:
            self.assertGreaterEqual(center_y - 50, 20)
            self.assertLessEqual(center_y + 50, 1030)

    def test_level5_keeps_the_same_spacing_through_all_four_boss_choices(self):
        self.assertEqual(get_boss_vertical_spacing(5, 4), LEVEL5_BOSS_VERTICAL_SPACING)
        possible_anchor_centers = [700, 700 - LEVEL5_BOSS_VERTICAL_SPACING]
        for position in range(1, 4):
            next_anchor_centers = []
            for anchor_y in possible_anchor_centers:
                positions = build_next_boss_positions(
                    anchor_center=(350 + (position - 1) * 200, anchor_y),
                    choice_count=2,
                    vertical_spacing=LEVEL5_BOSS_VERTICAL_SPACING,
                    screen_height=1050,
                )

                self.assertEqual(anchor_y - positions[0][1], LEVEL5_BOSS_VERTICAL_SPACING)
                self.assertEqual(
                    positions[0][1] - positions[1][1],
                    LEVEL5_BOSS_VERTICAL_SPACING,
                )
                self.assertTrue(all(center_y - 50 >= 20 for _, center_y in positions))
                next_anchor_centers.extend(center_y for _, center_y in positions)
            possible_anchor_centers = next_anchor_centers

    def test_level5_reflows_saved_history_to_the_same_spacing(self):
        roster = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["11_Malthus.png", "12_Ricardo.png"],
        ]
        old_history = [
            {"filename": "3_RobertFulton.png", "rect": pygame.Rect(350, 500, 100, 100)},
            {"filename": "5_SamuelSlater.png", "rect": pygame.Rect(550, 200, 100, 100)},
            {"filename": "9_Laffitte.png", "rect": pygame.Rect(750, -100, 100, 100)},
        ]

        layout = rebuild_boss_route_layout(
            roster,
            old_history,
            LEVEL5_BOSS_VERTICAL_SPACING,
            1050,
        )

        centers = [entry["rect"].center for entry in layout["defeated_bosses"]]
        self.assertEqual(centers, [(400, 610), (600, 430), (800, 250)])
        self.assertEqual(layout["last_defeated_rect"].center, (800, 250))
        self.assertTrue(all(rect.top >= 20 for rect in [entry["rect"] for entry in layout["defeated_bosses"]]))

    def test_long_final_victory_content_stays_inside_result_window(self):
        lang = load_language("RU")
        window = pygame.Rect(560, 350, 560, 350)
        ok_button = pygame.Rect(1010, 628, 80, 42)

        layout = build_win_result_layout(
            self.font_path,
            [
                lang["RewardLevel5FinalBoss"],
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
