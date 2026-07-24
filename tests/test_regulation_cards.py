import unittest
from unittest import mock

import game_state
from gameplay_page import GameplayPage
from gameplay_price_helpers import (
    build_market_probabilities,
    build_stock_price_animation_queue,
)
from gameplay_turn import build_price_cards_processing_queue


class RegulationCardTests(unittest.TestCase):
    def test_regulation_forces_only_its_market_random_roll_flat(self):
        probabilities = build_market_probabilities(
            {0: {0: 1}, 1: {}, 2: {}},
            force_flat_markets={1},
        )

        self.assertNotEqual(probabilities[0]["flat"], 100)
        self.assertEqual(probabilities[1], {"fall": 0.0, "flat": 100.0, "rise": 0.0})
        self.assertNotEqual(probabilities[2]["flat"], 100)

    def test_non_random_forced_rise_overrides_regulation(self):
        queue = build_stock_price_animation_queue(
            2,
            3,
            4,
            forced_rise_markets={1},
            force_flat_markets={1},
        )

        self.assertEqual(queue[1], {"market": 1, "type": "rise", "price_change": 3})

    def test_regulation_and_gain_are_processed_independently(self):
        page = GameplayPage.__new__(GameplayPage)
        page.market_cards = {0: {0: 20, 1: 11}, 1: {}, 2: {}}
        page.market_card_turns = {0: {0: 2, 1: 1}, 1: {}, 2: {}}
        page.market_card_actions = {0: {}, 1: {}, 2: {}}
        page.card_actions = {11: 2}
        page.Aprice = page.BPrice = page.CPrice = 10
        page.price_card_queue = build_price_cards_processing_queue(
            page.market_cards,
            page.market_card_turns,
        )
        page.current_card_processing = page.price_card_queue.pop(0)
        page.card_processing_delay = 0
        page.card_processing_start_time = 0
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page._record_rebate_a_fall = lambda *args: False
        page._begin_effect_finalize_or_wait = lambda: None

        page.update_price_card_processing()
        self.assertEqual(page.Aprice, 10)
        self.assertEqual(page.market_card_turns[0][0], 1)

        page.update_price_card_processing()
        self.assertEqual(page.Aprice, 12)
        self.assertEqual(page.market_card_turns[0][1], 0)

    def test_shop_contract_uses_requested_chances_and_costs(self):
        with (
            mock.patch.object(game_state, "get_bought_shop_card_ids", return_value=set()),
            mock.patch.object(game_state, "build_gold_cards_pool", return_value=[]),
            mock.patch.object(game_state.random, "randint", return_value=1),
        ):
            pool = game_state.build_shop_card_offer_pool(3)

        self.assertIn(20, pool)
        self.assertIn(21, pool)
        self.assertEqual(game_state.SHOP_CARD_COSTS[20], 4)
        self.assertEqual(game_state.SHOP_CARD_COSTS[21], 6)


if __name__ == "__main__":
    unittest.main()
