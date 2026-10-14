import unittest
from unittest import mock

import game_state
import profile_manager
import pygame
from shop_page import ShopPage
from tests import test_market_copy_cards


class ProtectivePutTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.protective_put_charges = 0
        game_state.deal_flow_bonus_percent = 0
        self.page = test_market_copy_cards.MarketCopyCardTests.page()
        self.page._record_short_seller_falls = mock.Mock(return_value=False)
        self.page._record_rebate_a_fall = mock.Mock()
        self.page._record_c_price_fall = mock.Mock()

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def test_level_chance_capacity_and_reappearance(self):
        self.assertFalse(game_state.buy_protective_put(2))
        for level, roll, expected in ((2, 1, False), (3, 20, True), (3, 21, False)):
            with mock.patch.object(game_state.random, "randint", return_value=roll):
                self.assertEqual("protective_put" in game_state.build_shop_special_offer_pool(level, max_offers=100), expected)
        for _ in range(3):
            self.assertTrue(game_state.buy_protective_put(3))
        self.assertFalse(game_state.buy_protective_put(3))
        self.assertNotIn("protective_put", game_state._available_screening_offer_ids(3))
        game_state.consume_protective_put()
        self.assertIn("protective_put", game_state._available_screening_offer_ids(3))

    def test_purchase_save_display_and_run_reset(self):
        page = ShopPage.__new__(ShopPage)
        page.offers = [{"kind": "special", "special_id": "protective_put", "cost": 1}]
        page.sold_offer_indexes = set()
        page.level_number = 3
        game_state.napoleondors = 2
        page._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 1)
        self.assertEqual(game_state.get_protective_put_charges(), 1)
        profile_manager.apply_profile_to_game_state({"progress": profile_manager._capture_progress()})
        entries = [e for e in game_state.get_active_shop_offer_effects(3) if e["special_id"] == "protective_put"]
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0]["remaining"])
        game_state.reset_level_attempt(3)
        self.assertEqual(game_state.get_protective_put_charges(), 0)

    def test_only_actual_owned_falls_consume_protection(self):
        page = self.page
        game_state.buy_protective_put(3)
        page.Bquantity = 0
        page._apply_price_change(1, -2)
        self.assertEqual(page.BPrice, 22)
        page._apply_price_change(0, 2)
        self.assertEqual(game_state.get_protective_put_charges(), 1)
        page._apply_price_change(0, -2)
        self.assertEqual(page.Aprice, 14)
        self.assertEqual(game_state.get_protective_put_charges(), 0)
        self.assertTrue(page._is_protective_put_animating())
        page._apply_price_change(0, -2)
        self.assertEqual(page.Aprice, 12)

    def test_blue_chips_and_price_floor_preserve_charge(self):
        page = self.page
        game_state.buy_protective_put(3)
        page.market_cards[0][0] = 22
        page._apply_price_change(0, -2)
        self.assertEqual(page.Aprice, 12)
        page.CPrice = 2
        page._apply_price_change(2, -5)
        self.assertEqual(game_state.get_protective_put_charges(), 1)
        self.assertFalse(page._is_protective_put_animating())

    def test_three_falls_use_three_separate_charges(self):
        for _ in range(3):
            game_state.buy_protective_put(3)
        self.assertEqual(self.page._protect_put_prices((12, 24, 36), (2, 2, 2)), (12, 24, 36))
        self.assertEqual(game_state.get_protective_put_charges(), 0)

    def test_protected_market_waits_for_confirmation_without_timeout(self):
        page = self.page
        game_state.buy_protective_put(3)
        page.price_animation_queue = [{"market": 0, "type": "fall", "price_change": -2}]
        self.assertTrue(page._start_next_price_animation())
        self.assertEqual(page.Aprice, 12)
        self.assertEqual(page.current_price_animation["type"], "unchanged")
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=999999):
            with mock.patch.object(page, "update_price_animation") as update:
                page.update_gameplay()
                update.assert_not_called()
            self.assertTrue(page._is_protective_put_animating())
            page._acknowledge_protective_put()
            self.assertFalse(page._is_protective_put_animating())
            self.assertEqual(page.current_price_animation["last_update"], 999999)

    def test_ok_click_and_enter_acknowledge_one_message_without_click_through(self):
        page = self.page
        page.mouse_pos = mock.Mock(return_value=(15, 15))
        page.protective_put_pending = 2
        page.protective_put_ok_rect = pygame.Rect(10, 10, 100, 40)
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(15, 15))
        page.events = mock.Mock(return_value=[click, click])
        page.handle_input()
        self.assertEqual(page.protective_put_pending, 1)
        page.events.return_value = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        page.handle_input()
        self.assertEqual(page.protective_put_pending, 0)
