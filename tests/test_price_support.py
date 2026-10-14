import unittest
from unittest import mock

import game_state
import profile_manager
from gameplay_price_helpers import BASE_MARKET_PROBABILITIES, build_market_probabilities, build_stock_price_animation_queue
from gameplay_page import GameplayPage
from shop_page import ShopPage


class PriceSupportTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.active_price_support_rounds = []
        game_state.deal_flow_bonus_percent = 0

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def test_split_and_missing_donors(self):
        probs = build_market_probabilities(price_support_markets=(0, 1), price_support_bonus=4)
        self.assertEqual(probs[0], {"fall": 0, "flat": 11, "rise": 89})
        self.assertEqual(probs[1], {"fall": 8, "flat": 18, "rise": 74})
        self.assertEqual(probs[2], BASE_MARKET_PROBABILITIES[2])
        for fall, flat, expected in ((8, 0, (4, 0, 96)), (1, 8, (0, 5, 95)), (1, 1, (0, 0, 100))):
            probs = build_market_probabilities(
                base_probabilities={0: {"fall": fall, "flat": flat, "rise": 100-fall-flat}},
                price_support_markets=(0,), price_support_bonus=4,
            )[0]
            self.assertEqual(tuple(probs[k] for k in ("fall", "flat", "rise")), expected)

    def test_stacking_forced_flat_and_sampling(self):
        probs = build_market_probabilities(price_support_markets=(0,), price_support_bonus=12)
        self.assertEqual(probs[0]["rise"], 97)
        probs = build_market_probabilities(force_flat=True, price_support_markets=(0,), price_support_bonus=12)
        self.assertEqual(probs[0]["flat"], 100)
        probs = build_market_probabilities({0: {}}, force_flat_markets=(0,), price_support_markets=(0,), price_support_bonus=12)
        self.assertEqual(probs[0]["flat"], 100)
        with mock.patch("gameplay_price_helpers.random.random", return_value=0.13):
            queue = build_stock_price_animation_queue(1, 1, 1, price_support_markets=(0,), price_support_bonus=4)
        self.assertEqual(queue[0]["type"], "rise")
        self.assertEqual(queue[1]["type"], "unchanged")

    def test_separate_timers_capacity_save_and_reset(self):
        self.assertTrue(game_state.buy_price_support())
        game_state.advance_price_support_round()
        self.assertTrue(game_state.buy_price_support())
        game_state.advance_price_support_round()
        self.assertTrue(game_state.buy_price_support())
        self.assertFalse(game_state.buy_price_support())
        profile_manager.apply_profile_to_game_state({"progress": profile_manager._capture_progress()})
        self.assertEqual(game_state.get_active_price_support_rounds(), [3, 4, 5])
        entries = [e for e in game_state.get_active_shop_offer_effects(5) if e["special_id"] == "price_support"]
        self.assertEqual([e["remaining"] for e in entries], [3, 4, 5])
        self.assertNotIn("price_support", game_state._available_screening_offer_ids(5))
        for _ in range(3):
            game_state.advance_price_support_round()
        self.assertEqual(game_state.get_active_price_support_rounds(), [1, 2])
        self.assertTrue(game_state.is_price_support_offer_available())
        self.assertIn("price_support", game_state._available_screening_offer_ids(5))
        game_state.reset_level_attempt(5)
        self.assertEqual(game_state.get_active_price_support_rounds(), [])

    def test_pool_chance_and_purchase(self):
        for level in (1, 2, 5):
            for roll, expected in ((20, True), (21, False)):
                with mock.patch.object(game_state.random, "randint", return_value=roll):
                    self.assertEqual("price_support" in game_state.build_shop_special_offer_pool(level, max_offers=50), expected)
        page = ShopPage.__new__(ShopPage)
        page.offers = [{"kind": "special", "special_id": "price_support", "cost": 2}]
        page.sold_offer_indexes = set()
        page.level_number = 2
        game_state.napoleondors = 3
        page._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 1)
        self.assertEqual(game_state.get_active_price_support_rounds(), [5])
        self.assertIn(0, page.sold_offer_indexes)

    def test_holdings_use_current_quantities(self):
        page = GameplayPage.__new__(GameplayPage)
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 3
        self.assertEqual(page._price_support_markets(), {0, 2})
        page.Aquantity, page.Bquantity = 0, 1
        self.assertEqual(page._price_support_markets(), {1, 2})

    def test_copied_market_does_not_capture_or_duplicate_ownership_bonus(self):
        from tests.test_market_copy_cards import MarketCopyCardTests

        page = MarketCopyCardTests.page()
        page.Bquantity = 0
        game_state.buy_price_support()
        page.market_cards[1][0] = 23
        self.assertTrue(page._apply_market_copy_card(23, 1, 0))
        self.assertEqual(page.market_copy_snapshots[1]["probabilities"]["rise"], 85)
        self.assertEqual(page._stock_bot_probabilities()[1]["rise"], 85)
        page.Bquantity = 1
        self.assertEqual(page._stock_bot_probabilities()[1]["rise"], 89)
        page.Bquantity = 0
        self.assertEqual(page._stock_bot_probabilities()[1]["rise"], 85)
