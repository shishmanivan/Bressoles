import json
import csv
import tempfile
from pathlib import Path
import unittest
from unittest import mock

import game_state
import profile_manager
from game_stats import get_level_run_losses
from round_page import RoundPage
from shop_page import ShopPage
from gameplay_collection_views import offer_status


class PriceCutTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.price_cut_purchases_by_level = {}
        game_state.price_cut_assistance_shown_levels = set()
        game_state.price_cut_assistance_milestones = {}
        game_state.bill_of_exchange_offer_bought = False
        game_state.deal_flow_bonus_percent = 0

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def assistance_shop(self, level=5, losses=4, balance=5, discount=0):
        page = ShopPage.__new__(ShopPage)
        page.profile_slot = 1
        page.level_number = level
        page.level_run_losses = losses
        page.napoleondors = balance
        page.discount_percent = discount
        page.sold_offer_indexes = set()
        page._price_cut_assistance_pending = False
        page.offers = [{"kind": "card", "card_id": 401, "cost": 4},
                       {"kind": "special", "special_id": "trader", "cost": 0},
                       {"kind": "special", "special_id": "variance", "cost": 1}]
        return page

    def test_assistance_waits_for_four_losses_and_affordable_price(self):
        for level, losses, balance, discount, expected in (
            (5, 3, 10, 0, False), (5, 4, 4, 0, False), (5, 4, 5, 0, True),
            (6, 8, 5, 0, True), (7, 8, 5, 0, False), (2, 4, 2.5, 50, True),
        ):
            with self.subTest(level=level, losses=losses, balance=balance):
                page = self.assistance_shop(level, losses, balance, discount)
                page._ensure_price_cut_assistance()
                offers = [o for o in page.offers if o.get("special_id") == "price_cut"]
                self.assertEqual(bool(offers), expected)
                self.assertEqual(len(page.offers), 3)
                if expected:
                    self.assertEqual(offers[0]["cost"], balance)

    def test_assistance_is_once_per_milestone_on_display_not_purchase(self):
        page = self.assistance_shop()
        page._ensure_price_cut_assistance()
        self.assertNotIn(5, game_state.price_cut_assistance_shown_levels)
        with mock.patch("shop_page.profile_manager.save_progress_from_game_state") as save:
            page._record_price_cut_assistance_shown()
            page._record_price_cut_assistance_shown()
            save.assert_called_once_with(1)
        self.assertIn(5, game_state.price_cut_assistance_shown_levels)
        game_state.reset_level_attempt(5)
        profile_manager.apply_profile_to_game_state({"progress": json.loads(json.dumps(profile_manager._capture_progress()))})
        next_shop = self.assistance_shop()
        next_shop._ensure_price_cut_assistance()
        self.assertFalse(next_shop._price_cut_assistance_pending)
        other_level = self.assistance_shop(level=4)
        other_level._ensure_price_cut_assistance()
        self.assertTrue(other_level._price_cut_assistance_pending)

    def test_repeated_guarantees_follow_alternating_loss_intervals(self):
        for losses in range(28):
            page = self.assistance_shop(losses=losses)
            page._ensure_price_cut_assistance()
            self.assertEqual(page._price_cut_assistance_pending,
                             losses in (4, 9, 13, 18, 22, 27), losses)
            with mock.patch("shop_page.profile_manager.save_progress_from_game_state"):
                page._record_price_cut_assistance_shown()
            saved = json.loads(json.dumps(profile_manager._capture_progress()))
            profile_manager.apply_profile_to_game_state({"progress": saved})

    def test_delayed_guarantee_consumes_reached_milestones_together(self):
        page = self.assistance_shop(losses=13, balance=4)
        page._ensure_price_cut_assistance()
        self.assertFalse(page._price_cut_assistance_pending)
        page.napoleondors = 5
        page._ensure_price_cut_assistance()
        with mock.patch("shop_page.profile_manager.save_progress_from_game_state"):
            page._record_price_cut_assistance_shown()
        next_shop = self.assistance_shop(losses=13)
        next_shop._ensure_price_cut_assistance()
        self.assertFalse(next_shop._price_cut_assistance_pending)
        next_shop.level_run_losses = 18
        next_shop._ensure_price_cut_assistance()
        self.assertTrue(next_shop._price_cut_assistance_pending)

    def test_legacy_guarantee_counts_as_first_milestone(self):
        profile_manager.apply_profile_to_game_state({"progress": {
            "price_cut_assistance_shown_levels": [5],
        }})
        self.assertEqual(game_state.price_cut_assistance_milestones, {5: 1})
        page = self.assistance_shop(losses=9)
        page._ensure_price_cut_assistance()
        self.assertTrue(page._price_cut_assistance_pending)

    def test_reaching_balance_inside_shop_preserves_sold_offers_and_avoids_duplicates(self):
        page = self.assistance_shop(balance=4)
        page._ensure_price_cut_assistance()
        self.assertFalse(page._price_cut_assistance_pending)
        page.sold_offer_indexes = {1}
        page.napoleondors = 5
        page._ensure_price_cut_assistance()
        page._ensure_price_cut_assistance()
        self.assertEqual(page.offers[1]["special_id"], "trader")
        self.assertEqual(page.offers[2]["special_id"], "price_cut")
        existing = self.assistance_shop()
        existing.offers[2]["special_id"] = "price_cut"
        existing._ensure_price_cut_assistance()
        self.assertEqual(sum(o.get("special_id") == "price_cut" for o in existing.offers), 1)

    def test_existing_profile_stats_count_only_run_losses_of_selected_level(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.csv"
            fields = ["Уровень", "Раунд", "Сложность", "Поражения"]
            with path.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output, delimiter=";")
                writer.writerow(fields)
                writer.writerows([
                    [5, "Забег уровня", "LEVEL", 4],
                    [5, "Раунд 1", "E", 50],
                    [5, "Босс уровня", "LevelBoss", 50],
                    [5, "Поражение забега", "RunLoss", 4],
                    [4, "Забег уровня", "Level", 9],
                ])
            self.assertEqual(get_level_run_losses(5, path), 4)
            self.assertEqual(get_level_run_losses(4, path), 9)
            self.assertEqual(get_level_run_losses(6, path), 0)

    def test_level_limits_and_twenty_percent_pool_chance(self):
        game_state.price_cut_assistance_shown_levels = set(range(1, 7))
        self.assertEqual(game_state.get_shop_special_cost("price_cut", 1), 5)
        for level in (1, 2, 6, 7, 8):
            for roll in (20, 21):
                with mock.patch.object(game_state.random, "randint", return_value=roll):
                    pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
                self.assertEqual("price_cut" in pool, level <= 6 and roll <= 20)
            self.assertEqual("price_cut" in game_state._available_screening_offer_ids(level), level <= 6)
        self.assertFalse(game_state.buy_price_cut(7))

    def test_random_offers_stay_locked_even_with_legacy_purchases(self):
        for level in range(1, 7):
            game_state.buy_price_cut(level)
            with mock.patch.object(game_state.random, "randint", return_value=1):
                pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
            self.assertNotIn("price_cut", pool)
            self.assertNotIn("price_cut", game_state._available_screening_offer_ids(level))
            self.assertEqual(game_state.apply_price_cut_goal_modifier(100, level), 96)

    def test_random_pool_unlocks_only_after_affordable_guaranteed_display(self):
        page = self.assistance_shop(losses=0, balance=5)
        for losses in range(4):
            page.level_run_losses = losses
            page._ensure_price_cut_assistance()
            self.assertFalse(page._price_cut_assistance_pending)
            self.assertFalse(game_state.is_price_cut_random_offer_available(5))
        page.level_run_losses = 4
        page.napoleondors = 4
        page._ensure_price_cut_assistance()
        self.assertFalse(page._price_cut_assistance_pending)
        self.assertFalse(game_state.is_price_cut_random_offer_available(5))
        page.napoleondors = 5
        page._ensure_price_cut_assistance()
        self.assertTrue(page._price_cut_assistance_pending)
        self.assertFalse(game_state.is_price_cut_random_offer_available(5))
        with mock.patch("shop_page.profile_manager.save_progress_from_game_state"):
            page._record_price_cut_assistance_shown()
        saved = json.loads(json.dumps(profile_manager._capture_progress()))
        game_state.price_cut_assistance_shown_levels.clear()
        profile_manager.apply_profile_to_game_state({"progress": saved})
        for level in range(1, 7):
            with mock.patch.object(game_state.random, "randint", return_value=1):
                pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
            self.assertEqual("price_cut" in pool, level == 5)
            self.assertEqual("price_cut" in game_state._available_screening_offer_ids(level), level == 5)

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
