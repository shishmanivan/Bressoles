import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from asset_loaders import find_font_path_or_exit
from gameplay_page import (
    LEVEL6_BOT_ACTION_MS,
    LEVEL6_BOT_END_PRESS_MS,
    LEVEL6_BOT_THINK_MS,
    LEVEL6_EXPERIMENT_TURNS,
    GameplayPage,
)


class Level6AlternatingTurnTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 6
        page.is_boss_fight = True
        page.Day = 1
        page.LastTurn = LEVEL6_EXPERIMENT_TURNS
        page.level6_turn_owner = "player"
        page.level6_bot_turn_phase = None
        page.level6_bot_turn_started_at = 0
        page.stock_bot_acted_this_resolution = False
        return page

    def test_bot_turn_finishes_before_market_resolution_starts(self):
        page = self._page()
        page._run_stock_bot_turn = mock.Mock(
            return_value={
                "action": "trade",
                "sold": {"A": 2},
                "bought": {"B": 1},
            }
        )
        page._start_market_resolution_after_actions = mock.Mock()

        with mock.patch("pygame.time.get_ticks", return_value=100):
            page._begin_level6_bot_turn()

        self.assertEqual(page.level6_turn_owner, "bot")
        self.assertEqual(page.level6_bot_turn_phase, "thinking")
        page._start_market_resolution_after_actions.assert_not_called()

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS,
        ):
            self.assertTrue(page.update_level6_bot_turn())

        page._run_stock_bot_turn.assert_called_once_with()
        self.assertTrue(page.stock_bot_acted_this_resolution)
        self.assertEqual(page.level6_bot_turn_phase, "selling")
        page._start_market_resolution_after_actions.assert_not_called()

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS + LEVEL6_BOT_ACTION_MS,
        ):
            self.assertTrue(page.update_level6_bot_turn())

        self.assertEqual(page.level6_bot_turn_phase, "buying")
        page._start_market_resolution_after_actions.assert_not_called()

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS + LEVEL6_BOT_ACTION_MS * 2,
        ):
            self.assertTrue(page.update_level6_bot_turn())

        self.assertEqual(page.level6_bot_turn_phase, "ending")
        self.assertEqual(
            page.end_button_press_until,
            100 + LEVEL6_BOT_THINK_MS + LEVEL6_BOT_ACTION_MS * 2 + LEVEL6_BOT_END_PRESS_MS,
        )
        page._start_market_resolution_after_actions.assert_not_called()

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=(
                100
                + LEVEL6_BOT_THINK_MS
                + LEVEL6_BOT_ACTION_MS * 2
                + LEVEL6_BOT_END_PRESS_MS
            ),
        ):
            self.assertTrue(page.update_level6_bot_turn())

        self.assertEqual(page.level6_turn_owner, "market")
        self.assertIsNone(page.level6_bot_turn_phase)
        page._start_market_resolution_after_actions.assert_called_once_with()

    def test_bot_hold_is_shown_for_two_seconds_before_ending(self):
        page = self._page()
        page._run_stock_bot_turn = mock.Mock(return_value={"action": "hold"})
        page._start_market_resolution_after_actions = mock.Mock()

        with mock.patch("pygame.time.get_ticks", return_value=100):
            page._begin_level6_bot_turn()
        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS,
        ):
            page.update_level6_bot_turn()

        self.assertEqual(page.level6_bot_turn_phase, "holding")

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS + LEVEL6_BOT_ACTION_MS - 1,
        ):
            self.assertFalse(page.update_level6_bot_turn())
        self.assertEqual(page.level6_bot_turn_phase, "holding")

        with mock.patch(
            "pygame.time.get_ticks",
            return_value=100 + LEVEL6_BOT_THINK_MS + LEVEL6_BOT_ACTION_MS,
        ):
            self.assertTrue(page.update_level6_bot_turn())
        self.assertEqual(page.level6_bot_turn_phase, "ending")

    def test_end_turn_hands_control_to_bot_before_market_roll(self):
        page = self._page()
        page.win_lose_state = None
        page.turn_resolution_active = False
        page.effect_finalize_pending = False
        page.final_auto_liquidation_animation = None
        page.current_price_animation = None
        page.price_animation_queue = []
        page.current_card_processing = None
        page.price_card_queue = []
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page.side_card_jump_animations = {}
        page.lifecycle_card_jump_animations = {}
        page.market_clear_animations = []
        page.basket_trading_applied_this_resolution = False
        page.sideway_applied_this_resolution = False
        page.continuation_applied_this_resolution = False
        page.continuation_animation_phase = False
        page.c_price_fell_this_resolution = False
        page.manipulation_applied_this_resolution = False
        page.red_effects_applied_this_resolution = False
        page.short_seller_counted_markets_this_resolution = set()
        page.Aquantity = 2
        page.Bquantity = page.Cquantity = 0
        page._reset_drag_state = mock.Mock()
        page._start_end_button_press_animation = mock.Mock()
        page.arrow_sound = None
        page._try_start_waterloo_preview = mock.Mock(return_value=False)
        page._hold_hand_negative_overlays_until_next_turn = mock.Mock()
        page._begin_level6_bot_turn = mock.Mock()
        page._start_market_resolution_after_actions = mock.Mock()

        self.assertTrue(page._start_turn_resolution())

        self.assertTrue(page.turn_resolution_active)
        page._begin_level6_bot_turn.assert_called_once_with()
        page._start_market_resolution_after_actions.assert_not_called()

    def test_bot_trades_on_turn_seven_and_liquidates_on_turn_eight(self):
        page = self._page()
        page.stock_bot_enabled = True
        page.stock_bot_type = "reinvestment"
        page.stock_bot = mock.Mock()
        page.stock_bot.display_name = "Bot3"
        page.stock_bot.trade.return_value = {"action": "hold"}
        page.stock_bot.sell_all.return_value = {"action": "liquidate"}
        page.Aprice = page.BPrice = page.CPrice = 4
        page._record_stock_bot_trade = mock.Mock()
        page._stock_bot_probabilities = mock.Mock(return_value={})

        page.Day = 7
        self.assertTrue(page._run_stock_bot_turn())
        page.stock_bot.trade.assert_called_once()
        page.stock_bot.sell_all.assert_not_called()

        page.stock_bot.reset_mock()
        page.stock_bot.sell_all.return_value = {"action": "liquidate"}
        page.Day = 8
        self.assertTrue(page._run_stock_bot_turn())
        page.stock_bot.sell_all.assert_called_once_with(page._current_prices())
        page.stock_bot.trade.assert_not_called()

    def test_regular_battle_keeps_existing_bot_timing(self):
        page = self._page()
        page.level_number = 5
        page.is_boss_fight = True
        page.Day = 7
        page.LastTurn = 8
        page.stock_bot_enabled = True
        page.stock_bot_type = "simple"
        page.stock_bot = mock.Mock()
        page.stock_bot.display_name = "Boss"
        page.stock_bot.sell_all.return_value = {"action": "liquidate"}
        page.Aprice = page.BPrice = page.CPrice = 4
        page._record_stock_bot_trade = mock.Mock()

        self.assertTrue(page._run_stock_bot_turn())

        page.stock_bot.sell_all.assert_called_once_with(page._current_prices())

    def test_level6_battle_starts_cardless_with_exactly_eight_turns(self):
        pygame.init()
        screen = pygame.display.set_mode((1680, 1050))
        self.addCleanup(pygame.quit)

        with mock.patch("gameplay_page.ensure_stats_file"):
            page = GameplayPage(
                screen,
                find_font_path_or_exit(),
                difficulty="e",
                goal=0,
                level_number=6,
                is_boss_fight=True,
                boss_index=0,
                defeated_count=0,
                boss_filename="2_AdamSmith.png",
                test_mode=True,
                active_silver_cards=[201],
                active_black_cards=[301],
                active_gold_cards=[401],
                active_lifecycle_card_order=[
                    {"kind": "silver", "card_id": 201},
                    {"kind": "black", "card_id": 301},
                    {"kind": "gold", "card_id": 401},
                ],
                positioning_start_cards=[1, 2],
                rounds_required=0,
            )

        self.assertEqual(page.LastTurn, 8)
        self.assertEqual(page.hand, 0)
        self.assertEqual(page.deck, [])
        self.assertEqual(page.hand_cards, [])
        self.assertEqual(page.shareholder_effect_count, 0)
        self.assertEqual(page.active_silver_cards, [])
        self.assertEqual(page.active_black_cards, [])
        self.assertEqual(page.active_gold_cards, [])
        self.assertEqual(page.active_lifecycle_card_order, [])


if __name__ == "__main__":
    unittest.main()
