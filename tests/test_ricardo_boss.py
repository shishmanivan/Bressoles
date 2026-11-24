import unittest
from types import SimpleNamespace
from unittest import mock

import pygame

import game_state
from boss_logic import BOSS_LEVELS, apply_boss_functionality, apply_boss_reward
from gameplay_layout import build_market_placeholders
from gameplay_page import GameplayPage


class RicardoBossTests(unittest.TestCase):
    def setUp(self):
        self.original_gold_cards = list(game_state.gold_cards)
        game_state.gold_cards = []

    def tearDown(self):
        game_state.gold_cards = self.original_gold_cards

    def test_ricardo_is_a_category_two_boss(self):
        self.assertEqual(BOSS_LEVELS["12_Ricardo.png"], 2)

    def test_gold_rebate_percentage_is_visible_without_disclosure(self):
        page = GameplayPage.__new__(GameplayPage)
        page._get_current_rebate_sale_percent = mock.Mock(return_value=146)
        with mock.patch.object(game_state, "is_disclosure_active", return_value=False):
            self.assertIn("146%", page._get_disclosure_card_tooltip_content(407)[1])
            self.assertIsNone(page._get_disclosure_card_tooltip_content(302))

    def test_ricardo_reduces_each_market_from_three_slots_to_two(self):
        gameplay = SimpleNamespace(boss_market_slots_per_market=3)
        apply_boss_functionality("TwoMarketSlots", gameplay)

        placeholders = build_market_placeholders(
            pygame.Rect(0, 0, 500, 300),
            market=1,
            num_placeholders=gameplay.boss_market_slots_per_market,
        )

        self.assertEqual(gameplay.boss_market_slots_per_market, 2)
        self.assertEqual([entry["slot"] for entry in placeholders], [0, 1])
        self.assertTrue(all(entry["market"] == 1 for entry in placeholders))

    def test_reward_selects_from_rare_gold_pool(self):
        gameplay = SimpleNamespace(last_earned_cards=[])
        with (
            mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[401]) as build_pool,
            mock.patch.object(game_state.random, "choice", return_value=401) as choose,
        ):
            apply_boss_reward("RandomGoldCard", gameplay)

        build_pool.assert_called_once_with(None)
        choose.assert_called_once_with([401])
        self.assertEqual(game_state.gold_cards, [401])
        self.assertEqual(gameplay.last_earned_cards, [401])

    def test_empty_probability_pool_does_not_use_an_unrolled_fallback(self):
        with (
            mock.patch.object(game_state, "build_gold_cards_pool", return_value=[]),
            mock.patch.object(game_state, "build_open_gold_cards_pool") as fallback_pool,
            mock.patch.object(game_state.random, "choice") as choose,
        ):
            self.assertIsNone(game_state.add_random_gold_card())

        fallback_pool.assert_not_called()
        choose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
