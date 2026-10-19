import json
import unittest
from unittest import mock

import game_state
import profile_manager
from round_page import RoundPage
from shop_page import ShopPage
from gameplay_collection_views import offer_status


class PriceCutTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.price_cut_purchases_by_level = {}
        game_state.deal_flow_bonus_percent = 0

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def test_level_limits_and_twenty_percent_pool_chance(self):
        self.assertEqual(game_state.get_shop_special_cost("price_cut", 1), 5)
        for level in (1, 2, 6, 7, 8):
            for roll in (20, 21):
                with mock.patch.object(game_state.random, "randint", return_value=roll):
                    pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
                self.assertEqual("price_cut" in pool, level <= 6 and roll <= 20)
            self.assertEqual("price_cut" in game_state._available_screening_offer_ids(level), level <= 6)
        self.assertFalse(game_state.buy_price_cut(7))

    def test_reductions_stack_only_for_purchased_level_and_survive_runs(self):
        self.assertTrue(game_state.buy_price_cut(5))
        self.assertEqual(game_state.apply_price_cut_goal_modifier(100, 5), 96)
        self.assertEqual(game_state.apply_price_cut_goal_modifier(100, 6), 100)
        game_state.buy_price_cut(5)
        self.assertEqual(game_state.apply_price_cut_goal_modifier(10000, 5), 9216)
        game_state.reset_level_attempt(5)
        game_state.complete_level_run(5)
        saved = json.loads(json.dumps(profile_manager._capture_progress()))
        game_state.price_cut_purchases_by_level.clear()
        profile_manager.apply_profile_to_game_state({"progress": saved})
        self.assertEqual(game_state.get_price_cut_purchases(5), 2)
        self.assertEqual(game_state.apply_price_cut_goal_modifier(1, 5), 1)
        self.assertIsNone(game_state.apply_price_cut_goal_modifier(None, 5))

    def test_purchase_and_active_offer_status(self):
        page = ShopPage.__new__(ShopPage)
        page.level_number = 3
        page.offers = [{"kind": "special", "special_id": "price_cut", "cost": 5}]
        page.sold_offer_indexes = set()
        game_state.napoleondors = 5
        page._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 0)
        self.assertEqual(game_state.get_price_cut_purchases(3), 1)
        self.assertIn(0, page.sold_offer_indexes)
        entries = [entry for entry in game_state.get_active_shop_offer_effects(3)
                   if entry["special_id"] == "price_cut"]
        self.assertEqual(len(entries), 1)
        view = mock.Mock()
        view._get_text.side_effect = lambda key, fallback: fallback
        self.assertEqual(offer_status(view, entries[0]), "Навсегда для этого уровня")
        self.assertFalse(any(entry["special_id"] == "price_cut"
                             for entry in game_state.get_active_shop_offer_effects(7)))

    def test_round_selection_displays_reduced_goals_without_reapplying(self):
        page = RoundPage.__new__(RoundPage)
        page.level_number = 5
        page.defeated_count = 0
        page.base_button_goals = {"E": 100, "M": 200, "H": None}
        game_state.buy_price_cut(5)
        game_state.clear_bailout_bonus()
        game_state.clear_loan_offers()
        game_state.clear_insurance_goal_debt()
        for _ in range(2):
            self.assertEqual(page._build_display_button_goals(), {"E": 96, "M": 192, "H": None})
