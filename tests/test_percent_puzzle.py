import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
from gameplay_deck import InvestedCard
from gameplay_page import GameplayPage
from gameplay_trade_actions import apply_ordered_rebate_modifiers


class PercentPuzzleTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.black_cards = [301, 302, 303, 304]
        game_state.active_black_cards = [304]
        game_state.silver_cards = [221]
        game_state.gold_cards = [438]
        game_state.active_gold_cards = [438]
        game_state.round_reward_cards = {6: [126]}
        game_state.napoleondors = 5
        game_state.windfall_boss_victories = 0
        game_state.risk_premium_h_rounds = 0

    def tearDown(self):
        profile = profile_manager._default_profile(1)
        profile["progress"] = self.progress
        profile_manager.apply_profile_to_game_state(profile)

    def page(self, order=(221, 304, 438)):
        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = [card for card in order if 200 < card < 300]
        page.active_black_cards = [card for card in order if 300 < card < 400]
        page.active_gold_cards = [card for card in order if 400 < card < 500]
        page.active_lifecycle_card_order = [
            {"card_id": card, "kind": "silver" if card < 300 else "black" if card < 400 else "gold"}
            for card in order
        ]
        page.side_cards_top = [InvestedCard(126, deck_origin="temporary"), None]
        page.side_card_origins_top = {0: 1}
        page.side_cards_locked_top = {0: False}
        page.side_card_jump_animations = {}
        page.lifecycle_card_jump_animations = {}
        page.hand_cards = []
        page.last_earned_cards = []
        page.rebate_a_fall_bonus_percent = 0
        page.level_number = 6
        page.Day = 2
        page.pending_draws = 1
        return page

    def test_puzzle_consumes_equipped_pieces_and_replaces_black_inventory(self):
        page = self.page()
        self.assertTrue(page._try_complete_percent_puzzle())
        self.assertEqual(page._active_lifecycle_cards(), [])
        self.assertEqual(page.side_cards_top, [None, None])
        self.assertEqual(game_state.black_cards, [301, 302, 303, 305])
        self.assertEqual(game_state.silver_cards, [])
        self.assertEqual(game_state.gold_cards, [])
        self.assertEqual(game_state.round_reward_cards[6], [])
        self.assertEqual(page.last_earned_cards, [305])
        self.assertEqual(page.pending_draws, 1)
        self.assertFalse(page._try_complete_percent_puzzle())
        self.assertEqual(page.last_earned_cards, [305])
        rows = page._get_card_report_rows()
        self.assertEqual(rows[0]["card_id"], 305)
        self.assertIn("Rebate", rows[0]["label"])

    def test_all_four_must_be_placed_not_merely_owned_or_in_hand(self):
        for absent in (221, 304, 438, 126):
            with self.subTest(absent=absent):
                page = self.page(tuple(c for c in (221, 304, 438) if c != absent))
                if absent == 126:
                    page.side_cards_top = [None]
                    page.hand_cards = [126]
                self.assertFalse(page._try_complete_percent_puzzle())
                self.assertIn(304, game_state.black_cards)

    def test_one_copy_consumed_and_unrelated_cards_keep_their_order(self):
        game_state.silver_cards = [221, 221]
        game_state.gold_cards = [438, 438, 413]
        page = self.page((438, 221, 413, 304, 221, 438))
        self.assertTrue(page._try_complete_percent_puzzle())
        self.assertEqual(page._active_lifecycle_cards(), [413, 221, 438])
        self.assertEqual(game_state.silver_cards, [221])
        self.assertEqual(game_state.gold_cards, [438, 413])

    def test_full_black_inventory_does_not_prevent_replacement(self):
        game_state.black_cards = [304] + list(range(310, 317))
        self.assertTrue(self.page()._try_complete_percent_puzzle())
        self.assertEqual(len(game_state.black_cards), 8)
        self.assertEqual(game_state.black_cards[0], 305)

    def test_completed_reward_migration_does_not_restore_consumed_quarter(self):
        self.page()._try_complete_percent_puzzle()
        profile = profile_manager._default_profile(1)
        profile["progress"] = profile_manager._capture_progress()
        profile["progress"]["level_5_boss_defeated"] = True
        profile_manager._migrate_completed_black_rewards(profile)
        self.assertNotIn(304, profile["progress"]["black_cards"])
        self.assertEqual(game_state.get_level_completion_black_reward_cards(5), [303])

    def test_ordered_addition_and_multiplier(self):
        self.assertEqual(apply_ordered_rebate_modifiers(150, [("add", 20), ("multiply", 3)]), 510)
        self.assertEqual(apply_ordered_rebate_modifiers(150, [("multiply", 3), ("add", 20)]), 470)
        # Gold + silver + red Rebate synergy is always the base, regardless of slots.
        for order, expected in [((407, 201, 410, 305), 480),
                                ((305, 410, 201, 407), 460)]:
            page = self.page(order)
            page.side_cards_top = [110]
            self.assertEqual(page._get_current_rebate_sale_percent(), expected)

    def test_catalyst_efficiency_and_shareholders_follow_slots(self):
        page = self.page((407, 210, 435, 305, 423))
        page.efficiency_bonus_percent = 4
        page.hand_cards = [100]
        # (130 + Catalyst 10 + Efficiency 4) * 3 + Stewardship 20.
        self.assertEqual(page._get_current_rebate_sale_percent(), 452)
        page = self.page((407, 305, 210, 435, 423))
        page.efficiency_bonus_percent = 4
        page.hand_cards = [100]
        self.assertEqual(page._get_current_rebate_sale_percent(), 424)

    def test_multiplier_needs_rebate_and_jumps_only_during_liquidation(self):
        page = self.page((305,))
        self.assertIsNone(page._get_current_rebate_sale_percent())
        page = self.page((201, 305))
        page._start_card_jump_animation = mock.Mock()
        self.assertEqual(page._get_current_rebate_sale_percent(), 300)
        page._start_card_jump_animation.assert_not_called()
        page._start_rebate_card_jump_animations()
        self.assertEqual([call.args[1] for call in page._start_card_jump_animation.call_args_list], [0, 1])

    def test_consumed_red_still_counts_as_played_for_efficiency(self):
        page = self.page((221, 304, 438, 435))
        page._try_complete_percent_puzzle()
        self.assertEqual(page._record_efficiency_turn_bonus(), 4)

    def test_puzzle_reward_report_is_available_after_defeat(self):
        page = self.page()
        page._try_complete_percent_puzzle()
        page.win_lose_state = "lose"
        page.result_report_stage = "cards"
        self.assertFalse(page._has_result_report())
        page.result_report_stage = "card_report"
        self.assertTrue(page._has_result_report())

    def test_combined_game_save_restores_consumption_and_report(self):
        import pygame
        import gameplay_page
        from asset_loaders import find_font_path_or_exit
        pygame.init()
        self.addCleanup(pygame.quit)
        screen = pygame.display.set_mode((1680, 1050))
        game_state.level_5_boss_defeated = True
        with mock.patch.object(gameplay_page, "ensure_stats_file"):
            page = GameplayPage(screen, find_font_path_or_exit(), difficulty="e", goal=100,
                                level_number=6, test_mode=True, active_silver_cards=[221],
                                active_black_cards=[304], active_gold_cards=[438])
            # Move the dealt instance to its actual playable side placeholder.
            for zone in (page.hand_cards, page.deck):
                for index, card in enumerate(zone):
                    if card == 126:
                        zone[index] = None
                        break
            page.deck = [card for card in page.deck if card is not None]
            page.side_cards_top[0] = InvestedCard(126, deck_origin="temporary")
            self.assertTrue(page._try_complete_percent_puzzle())
            state = page._serialize_gameplay_state()
            restored = GameplayPage(screen, find_font_path_or_exit(), difficulty="e", goal=100,
                                    level_number=6, test_mode=True, saved_state=state,
                                    active_silver_cards=page.active_silver_cards,
                                    active_black_cards=page.active_black_cards,
                                    active_gold_cards=page.active_gold_cards,
                                    active_lifecycle_card_order=page.active_lifecycle_card_order)
        self.assertEqual(restored.percent_puzzle_completed_day, page.Day)
        self.assertEqual(restored.last_earned_cards, [305])
        self.assertNotIn(126, restored.side_cards_top)
        self.assertNotIn(304, restored._active_lifecycle_cards())
        self.assertFalse(restored._try_complete_percent_puzzle())
