import unittest
from unittest import mock

import game_state
from gameplay_page import GameplayPage
from gameplay_price_helpers import (
    build_market_probabilities,
    build_stock_price_animation_queue,
)


class BlueChipsCardTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.market_cards = {0: {}, 1: {}, 2: {0: 22}}
        page.market_card_turns = {0: {}, 1: {}, 2: {}}
        page.market_card_actions = {0: {}, 1: {}, 2: {}}
        page.market_cards_locked = {0: {}, 1: {}, 2: {0: True}}
        page.side_cards_top = [None] * 6
        page.side_cards_locked_top = {}
        page.side_card_jump_animations = {}
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page.active_silver_cards = []
        page.active_black_cards = []
        page.active_gold_cards = []
        page.active_lifecycle_card_order = []
        page.c_price_fell_this_resolution = False
        page._record_rebate_a_fall = mock.Mock(return_value=False)
        page._record_c_price_fall = mock.Mock(return_value=False)
        page._record_short_seller_falls = mock.Mock(return_value=False)
        return page

    def test_fall_probability_is_split_evenly_between_flat_and_rise(self):
        probabilities = build_market_probabilities(
            {0: {}, 1: {0: 22}, 2: {}},
            prevent_fall_markets={1},
        )

        self.assertEqual(
            probabilities[1],
            {"fall": 0.0, "flat": 25.0, "rise": 75.0},
        )

    def test_zero_fall_probability_can_never_roll_a_fall(self):
        with mock.patch("gameplay_price_helpers.random.random", return_value=0.0):
            queue = build_stock_price_animation_queue(
                2,
                3,
                4,
                prevent_fall_markets={2},
            )

        self.assertNotEqual(queue[2]["type"], "fall")

    def test_market_and_gain_drop_falls_are_blocked_but_growth_is_allowed(self):
        page = self._page()
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30

        page._apply_price_change(2, -4)
        self.assertEqual(page.CPrice, 30)
        page._apply_price_change(2, 4)
        self.assertEqual(page.CPrice, 34)

        page.market_cards[2][1] = 15
        page.market_card_turns[2][1] = 1
        page.card_actions = {15: -2}
        page.current_card_processing = (2, 1)
        page.price_card_queue = []
        page.card_processing_start_time = 0
        page.card_processing_delay = 0
        page._begin_effect_finalize_or_wait = mock.Mock()
        page.update_price_card_processing()

        self.assertEqual(page.CPrice, 34)
        self.assertEqual(page.market_card_turns[2][1], 0)
        self.assertNotIn(1, page.card_jump_animations[2])

    def test_crash_bankruptcy_and_low_bid_cannot_reduce_blue_chip_price(self):
        page = self._page()
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page._start_card_jump_animation = mock.Mock()

        page.side_cards_top[0] = 115
        page.side_cards_locked_top[0] = False
        self.assertFalse(page._apply_bankruptcy_effects_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 20, 30))

        page.side_cards_top[0] = 117
        self.assertTrue(page._apply_market_crash_effect_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (2, 2, 30))

        page.Aprice, page.BPrice, page.CPrice = 50, 50, 50
        page.side_cards_top[0] = 118
        self.assertTrue(page._apply_bid_effect_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 10, 50))

    def test_parity_uses_blue_chip_price_but_does_not_lower_it(self):
        page = self._page()
        page.Aprice, page.BPrice, page.CPrice = 10, 11, 20
        page.side_cards_top[0] = 123
        page.side_cards_locked_top[0] = False
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_parity_effect_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (14, 14, 20))

    def test_shop_contract_uses_eighteen_percent_chance_and_four_cost(self):
        with (
            mock.patch.object(game_state, "get_bought_shop_card_ids", return_value=set()),
            mock.patch.object(game_state, "build_gold_cards_pool", return_value=[]),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 18, 100],
            ),
        ):
            self.assertEqual(game_state.build_shop_card_offer_pool(3), [22])

        self.assertEqual(game_state.SHOP_CARD_COSTS[22], 4)


if __name__ == "__main__":
    unittest.main()
