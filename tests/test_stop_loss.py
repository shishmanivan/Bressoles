import unittest
from unittest import mock

import game_state
from tests.test_red_card_effects import RedCardEffectTests


class StopLossTests(unittest.TestCase):
    def page(self, active=True):
        page = RedCardEffectTests._page()
        page.active_silver_cards = [225, 225] if active else []
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page.Aquantity, page.Bquantity, page.Cquantity = 3, 4, 5
        page.Money = 7
        page._start_card_jump_animation = mock.Mock()
        return page

    def test_bankruptcy_sells_only_affected_holdings_at_old_price(self):
        page = self.page()
        page._set_market_price_to_minimum(1)
        self.assertEqual(page.Money, 87)
        self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), (3, 0, 5))
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 2, 30))
        page._set_market_price_to_minimum(1)
        self.assertEqual(page.Money, 87)

    def test_crash_sells_all_holdings_once(self):
        page = self.page()
        page.side_cards_top[0] = 117
        page._apply_market_crash_effect_if_needed()
        self.assertEqual(page.Money, 267)
        self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), (0, 0, 0))
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (2, 2, 2))

    def test_protected_and_already_minimum_stocks_are_not_sold(self):
        page = self.page()
        page.Aprice = 2
        page._apply_stop_loss_before_collapse((2, 20, 30), (2, 20, 2))
        self.assertEqual(page.Money, 157)
        self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), (3, 4, 0))

    def test_without_card_no_sale(self):
        page = self.page(False)
        page._set_market_price_to_minimum(0)
        self.assertEqual((page.Money, page.Aquantity, page.Aprice), (7, 3, 2))

    def test_license_and_pool_threshold(self):
        with mock.patch.object(game_state, 'licensed_card_ids', set()), mock.patch.object(game_state, 'is_level_completed', return_value=False):
            self.assertNotIn(225, game_state.build_license_offer_pool(6))
            self.assertIn(225, game_state.build_license_offer_pool(7))
            self.assertIn(225, game_state.build_license_offer_pool(8))
            self.assertEqual(game_state.get_license_cost(225), 5)
            game_state.licensed_card_ids.add(225)
            with mock.patch.object(game_state, 'load_cards_config', return_value={225: {'Type': 3, 'Open': 1, 'Variable': 10}}), mock.patch.object(game_state, 'get_rare_card_pool_chance', side_effect=lambda x: x), mock.patch.object(game_state.random, 'randint', return_value=10) as roll:
                self.assertEqual(game_state.build_silver_cards_pool(6), [])
                self.assertEqual(game_state.build_silver_cards_pool(7), [225])
                roll.return_value = 11
                self.assertEqual(game_state.build_silver_cards_pool(7), [])
