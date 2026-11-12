import unittest
from unittest import mock

import game_state
import localization
from gameplay_deck import InvestedCard
from shop_page import CARD_DESCRIPTIONS
from silver_black_page import CARD_TOOLTIPS
from tests import test_lifecycle_effects


class UpliftTests(unittest.TestCase):
    def page(self, order):
        page = test_lifecycle_effects.LifecycleEffectTests._page(
            silver=[card for card in order if card == 204],
            gold=[card for card in order if card != 204],
        )
        page.active_lifecycle_card_order = [
            {'kind': 'silver' if card == 204 else 'gold', 'card_id': card} for card in order
        ]
        page.card_actions = {11: 2, 15: -2, 17: 2}
        page._apply_contango_gain_drop_bonuses()
        return page

    def test_additions_and_left_to_right_multipliers(self):
        for order, expected in (([443], 4), ([444], 6), ([443, 444], 8),
                                ([443, 443], 6), ([443, 204], 8), ([204, 443], 6)):
            page = self.page(order)
            self.assertEqual(page._get_card_action(11), expected)
            self.assertEqual(page._get_card_action(15), -expected)
            self.assertEqual(page._get_card_action(17), expected)

    def test_investment_and_leverage_in_slot_order(self):
        for order, expected in (([443, 442], 10), ([442, 443], 8)):
            page = self.page(order)
            self.assertEqual(page._get_card_action(InvestedCard(11, 1)), expected)
            self.assertEqual(page._get_card_action(InvestedCard(15, 1)), -expected)
            self.assertEqual(page._get_card_action(11), 4)

    def test_accumulation_doubles_the_action_already_calculated_in_slot_order(self):
        for order, expected in (([204, 443], 12), ([443, 204], 16)):
            for card_id, sign in ((11, 1), (15, -1), (17, 1)):
                with self.subTest(order=order, card_id=card_id):
                    page = self.page(order)
                    page.accumulation_pending_sources = [0]
                    page.side_cards_top = [124]
                    page.side_cards_locked_top = {}
                    page.side_card_jump_animations = {}
                    page.market_card_actions = {0: {0: page._get_card_action(card_id)}}
                    page.market_card_turns = {0: {0: 1}}
                    page.market_cards_locked = {0: {}}
                    page.card_turns = {card_id: 1}
                    self.assertTrue(page._consume_accumulation_charge(card_id, 0, 0))
                    self.assertEqual(page.market_card_actions[0][0], sign * expected)
                    self.assertEqual(page.market_card_turns[0][0], 2)

    def test_catalog_and_pool_thresholds(self):
        for card, level, cost, chance in ((443, 3, 4, 25), (444, 5, 5, 5)):
            self.assertEqual(game_state.SHOP_CARD_COSTS[card], cost)
            config = {card: game_state.load_cards_config()[card]}
            self.assertEqual(config[card], {'Type': 5, 'Open': 1, 'Variable': str(chance)})
            with mock.patch.object(game_state, 'load_cards_config', return_value=config):
                with mock.patch.object(game_state.random, 'randint', return_value=chance):
                    self.assertEqual(game_state.build_gold_cards_pool(level), [card])
                    for locked_level in range(1, level):
                        self.assertEqual(game_state.build_gold_cards_pool(locked_level), [])
                        self.assertNotIn(card, game_state.build_open_gold_cards_pool(locked_level))
                with mock.patch.object(game_state.random, 'randint', return_value=chance+1):
                    self.assertEqual(game_state.build_gold_cards_pool(level), [])
            description = CARD_DESCRIPTIONS[card]
            self.assertEqual(CARD_TOOLTIPS[card][1], description)
            for language in localization.SUPPORTED_LANGUAGES:
                catalog, _, _ = localization._catalog(language)
                self.assertIn(description, catalog)

    def test_all_amplifiers_follow_display_order_independently_of_inventory(self):
        from itertools import permutations
        for order in permutations((204, 442, 443, 444)):
            page = self.page(order)
            # Inventory order differs from the explicit order of active slots.
            page.active_gold_cards = [444, 443, 442]
            for investment in (0, 1):
                expected = 2 + investment
                for modifier in order:
                    if modifier == 204 or (modifier == 442 and investment):
                        expected *= 2
                    elif modifier in (443, 444):
                        expected += {443: 2, 444: 4}[modifier]
                for card_id, sign in ((11, 1), (15, -1), (17, 1)):
                    with self.subTest(order=order, investment=investment, card=card_id):
                        self.assertEqual(
                            page._get_card_action(InvestedCard(card_id, investment)),
                            sign * expected,
                        )
