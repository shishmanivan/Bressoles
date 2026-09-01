import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
from boss_logic import BOSS_LEVELS, apply_boss_functionality, apply_boss_reward
from game_data import load_boss_rewards
from gameplay_page import GameplayPage


class AstorBossTests(unittest.TestCase):
    def setUp(self):
        self.original_bonus = game_state.boss_rare_card_pool_bonus_percent
        self.original_silver_level = game_state.active_silver_cards_level
        self.original_silver_deck = copy.deepcopy(game_state.active_silver_cards_deck)
        game_state.boss_rare_card_pool_bonus_percent = 0

    def tearDown(self):
        game_state.boss_rare_card_pool_bonus_percent = self.original_bonus
        game_state.active_silver_cards_level = self.original_silver_level
        game_state.active_silver_cards_deck = self.original_silver_deck

    def test_astor_is_a_category_one_boss_with_configured_effects(self):
        self.assertEqual(BOSS_LEVELS["15_Astor.png"], 1)
        self.assertEqual(
            load_boss_rewards()[15],
            {
                "Reward": "RareCardPoolPlus10",
                "Functionalities": "BurnCashEndTurn",
            },
        )

    def test_astor_burns_all_cash_at_end_of_turn(self):
        page = GameplayPage.__new__(GameplayPage)
        page.boss_burns_cash_end_turn = False
        page.win_lose_state = None
        page.Money = 17

        apply_boss_functionality("BurnCashEndTurn", page)

        self.assertTrue(page.boss_burns_cash_end_turn)
        self.assertEqual(page._burn_cash_for_astor_if_needed(), 17)
        self.assertEqual(page.Money, 0)

    def test_astor_reward_adds_ten_points_and_rebuilds_current_silver_pool(self):
        gameplay = mock.Mock(level_number=5)
        with mock.patch.object(game_state, "start_silver_cards_deck_for_level") as rebuild:
            apply_boss_reward("RareCardPoolPlus10", gameplay)

        self.assertEqual(game_state.get_boss_rare_card_pool_bonus(), 10)
        rebuild.assert_called_once_with(5)
        self.assertEqual(
            profile_manager._capture_progress()["boss_rare_card_pool_bonus_percent"],
            10,
        )

    def test_astor_bonus_applies_to_ordinary_silver_and_gold_pool_rolls(self):
        cards = {
            211: {"Type": 3, "Open": 1, "Variable": 5},
            414: {"Type": 5, "Open": 1, "Variable": 5},
        }
        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state, "is_card_licensed", return_value=True),
            mock.patch.object(game_state.random, "randint", return_value=15),
        ):
            self.assertNotIn(211, game_state.build_silver_cards_pool(5))
            self.assertNotIn(414, game_state.build_gold_cards_pool(5))

            game_state.boss_rare_card_pool_bonus_percent = 10

            self.assertIn(211, game_state.build_silver_cards_pool(5))
            self.assertIn(414, game_state.build_gold_cards_pool(5))

        with (
            mock.patch.object(game_state, "load_cards_config", return_value={}),
            mock.patch.object(game_state.random, "randint", return_value=15),
        ):
            game_state.boss_rare_card_pool_bonus_percent = 0
            self.assertNotIn(17, game_state.build_shop_card_offer_pool(3))

            game_state.boss_rare_card_pool_bonus_percent = 10
            self.assertIn(17, game_state.build_shop_card_offer_pool(3))


if __name__ == "__main__":
    unittest.main()
