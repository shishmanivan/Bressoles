import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import game_state
from asset_loaders import find_font_path_or_exit
from boss_logic import get_boss_number_from_filename, get_boss_number_from_index
from gameplay_winlose import apply_win_reward


class KnownRegressionTests(unittest.TestCase):
    def test_issue_price_is_visible_before_the_first_turn(self):
        import gameplay_page

        pygame.init()
        screen = pygame.display.set_mode((1680, 1050))
        self.addCleanup(pygame.quit)

        with mock.patch.object(gameplay_page, "ensure_stats_file"):
            page = gameplay_page.GameplayPage(
                screen,
                find_font_path_or_exit(),
                difficulty="e",
                goal=100,
                level_number=1,
                test_mode=True,
                active_gold_cards=[421],
                active_lifecycle_card_order=[{"kind": "gold", "card_id": 421}],
            )

        self.assertEqual(page.Day, 1)
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (6, 2, 2))

    def test_adam_smith_boss_round_reduces_last_turn_only_once(self):
        import gameplay_page

        previous_last_turn_bonus = game_state.global_last_turn_bonus
        previous_hand_bonus = game_state.global_hand_bonus
        pygame.init()
        screen = pygame.display.set_mode((1680, 1050))
        self.addCleanup(pygame.quit)
        self.addCleanup(setattr, game_state, "global_last_turn_bonus", previous_last_turn_bonus)
        self.addCleanup(setattr, game_state, "global_hand_bonus", previous_hand_bonus)
        game_state.global_last_turn_bonus = 0
        game_state.global_hand_bonus = 0

        with mock.patch.object(gameplay_page, "ensure_stats_file"):
            page = gameplay_page.GameplayPage(
                screen,
                find_font_path_or_exit(),
                difficulty="e",
                goal=100,
                level_number=2,
                is_boss_fight=True,
                boss_index=0,
                defeated_count=0,
                boss_filename="2_AdamSmith.png",
                test_mode=True,
                rounds_required=2,
            )

        self.assertEqual(page.LastTurn, 7)

    def test_missing_boss_functionality_has_no_hidden_index_fallback(self):
        import gameplay_page

        previous_last_turn_bonus = game_state.global_last_turn_bonus
        previous_hand_bonus = game_state.global_hand_bonus
        pygame.init()
        screen = pygame.display.set_mode((1680, 1050))
        self.addCleanup(pygame.quit)
        self.addCleanup(setattr, game_state, "global_last_turn_bonus", previous_last_turn_bonus)
        self.addCleanup(setattr, game_state, "global_hand_bonus", previous_hand_bonus)
        game_state.global_last_turn_bonus = 0
        game_state.global_hand_bonus = 0

        with (
            mock.patch.object(gameplay_page, "ensure_stats_file"),
            mock.patch.object(
                gameplay_page,
                "load_boss_rewards",
                return_value={2: {"Reward": "", "Functionalities": ""}},
            ),
        ):
            page = gameplay_page.GameplayPage(
                screen,
                find_font_path_or_exit(),
                difficulty="e",
                goal=100,
                level_number=2,
                is_boss_fight=True,
                boss_index=0,
                defeated_count=0,
                boss_filename="2_AdamSmith.png",
                test_mode=True,
                rounds_required=2,
            )

        self.assertEqual(page.LastTurn, 8)

    def test_resumed_dynamic_boss_reward_uses_saved_boss_identity(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = False
        gameplay.level_number = 3
        gameplay.boss_index = 0
        gameplay.defeated_count = 0
        gameplay.boss_filename = "6_Arkwright.png"
        gameplay.last_earned_cards = []
        apply_reward = mock.Mock()

        apply_win_reward(
            gameplay,
            earned_reward_cards={},
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=lambda: {6: {"Reward": "ArkwrightSilverCards"}},
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=apply_reward,
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
            get_boss_number_from_filename=get_boss_number_from_filename,
        )

        apply_reward.assert_called_once_with("ArkwrightSilverCards", gameplay)

    def test_resumed_dynamic_boss_stats_use_saved_boss_identity(self):
        import gameplay_page

        page = gameplay_page.GameplayPage.__new__(gameplay_page.GameplayPage)
        page.test_mode = False
        page._stats_recorded = False
        page.level_number = 3
        page.boss_index = 0
        page.defeated_count = 0
        page.Money = 0
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.Aprice = page.BPrice = page.CPrice = 2
        page.boss_filename = "6_Arkwright.png"
        page.round_num = None
        page.is_boss_fight = True
        page.difficulty = "e"

        with (
            mock.patch.object(gameplay_page, "update_game_stats") as update_stats,
            mock.patch.object(gameplay_page, "update_arkwright_stats") as update_arkwright_stats,
        ):
            page._record_stats_result(True)
            page._record_arkwright_stat("stolen")

        self.assertEqual(update_stats.call_args.args[:2], (3, 6))
        self.assertEqual(update_arkwright_stats.call_args.args[:2], (3, 6))

    def test_seventh_turn_advances_to_terminal_eighth_day(self):
        import gameplay_page

        page = gameplay_page.GameplayPage.__new__(gameplay_page.GameplayPage)
        page.turn_resolution_active = True
        page.effect_finalize_pending = True
        page.Day = 7
        page.LastTurn = 8
        page.win_lose_state = None
        page.red_effects_applied_this_resolution = True
        page.hand_compact_anim = None
        page.hand_draw_anim = None
        page._apply_boss_share_theft_if_needed = mock.Mock()
        page._run_stock_bot_turn = mock.Mock()
        def check_terminal_day():
            if page.Day >= page.LastTurn:
                page.win_lose_state = "lose"

        page._check_win_lose = mock.Mock(side_effect=check_terminal_day)
        page._is_final_auto_liquidation_animating = mock.Mock(return_value=False)
        page._draw_pending_cards = mock.Mock()
        page._save_active_game = mock.Mock()

        page._finalize_turn_resolution()

        self.assertEqual(page.Day, 8)
        self.assertEqual(page.win_lose_state, "lose")
        self.assertEqual(page._check_win_lose.call_count, 2)
        page._draw_pending_cards.assert_not_called()

    def test_black_futures_moves_terminal_day_from_eight_to_nine(self):
        import gameplay_page

        page = gameplay_page.GameplayPage.__new__(gameplay_page.GameplayPage)
        page.LastTurn = 8
        page._active_lifecycle_cards = mock.Mock(return_value=[301])

        page._apply_silver_last_turn_bonuses()

        self.assertEqual(page.LastTurn, 9)

    def test_rebate_liquidates_shares_only_when_terminal_day_arrives(self):
        import gameplay_page

        page = gameplay_page.GameplayPage.__new__(gameplay_page.GameplayPage)
        page.final_auto_liquidation_applied = False
        page.win_lose_state = None
        page.Day = 7
        page.LastTurn = 8
        page.Money = 10
        page.Aquantity = 2
        page.Bquantity = 1
        page.Cquantity = 0
        page.Aprice = 10
        page.BPrice = 20
        page.CPrice = 30
        page._has_active_silver_card = mock.Mock(return_value=False)
        page._has_played_side_card = mock.Mock(return_value=True)
        page._start_final_auto_liquidation_animation = mock.Mock()

        self.assertFalse(page._apply_final_auto_liquidation_if_needed())
        page._start_final_auto_liquidation_animation.assert_not_called()

        page.Day = 8
        self.assertTrue(page._apply_final_auto_liquidation_if_needed())
        liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
        self.assertEqual(liquidation["gross_value"], 40)
        self.assertEqual(liquidation["proceeds"], 36)
        self.assertEqual(liquidation["target_money"], 46)

    def test_every_configured_card_has_a_gameplay_field_tooltip(self):
        import gameplay_page
        from game_data import load_cards_config

        configured_cards = {int(card_id) for card_id in load_cards_config()}

        self.assertEqual(configured_cards - set(gameplay_page.FIELD_CARD_TOOLTIPS), set())

    def test_gameplay_field_tooltip_finds_cards_in_each_play_area(self):
        import gameplay_page

        page = gameplay_page.GameplayPage.__new__(gameplay_page.GameplayPage)
        page.deck_view_active = False
        page.dragged_card_source = None
        page.dragged_card_index = None
        page.dragged_card_side_slot = None
        page.dragged_card_market = None
        page.dragged_card_market_slot = None
        page.hand_cards = [117]
        page.bottom_placeholders = [{"slot": 0, "rect": pygame.Rect(0, 0, 20, 20)}]
        page.side_cards_top = [110]
        page.side_placeholders_top = [{"slot": 0, "rect": pygame.Rect(30, 0, 20, 20)}]
        page.side_placeholders_bottom = [{"slot": 0, "rect": pygame.Rect(60, 0, 20, 20)}]
        page.market_cards = {0: {0: 17}}
        page.market_placeholders = [
            {"market": 0, "slot": 0, "rect": pygame.Rect(90, 0, 20, 20)}
        ]
        page._active_lifecycle_cards = mock.Mock(return_value=[401])

        self.assertEqual(page._get_hovered_field_card((10, 10)), 117)
        self.assertEqual(page._get_hovered_field_card((40, 10)), 110)
        self.assertEqual(page._get_hovered_field_card((70, 10)), 401)
        self.assertEqual(page._get_hovered_field_card((100, 10)), 17)


if __name__ == "__main__":
    unittest.main()
