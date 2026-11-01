import unittest
from unittest import mock

import game_state
from gameplay_deck import InvestedCard, restore_card_instance, serialize_card_instance
from tests import test_lifecycle_effects
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS


class LeverageTests(unittest.TestCase):
    def test_only_invested_instances_are_doubled_with_contango_and_duplicates(self):
        for silver, gold, factor in (([], [], 1), ([], [442], 2),
                                     ([], [442, 442], 4), ([204], [442], 4)):
            page = test_lifecycle_effects.LifecycleEffectTests._page(silver=silver, gold=gold)
            page.card_actions = {11: 2, 15: -2, 17: 2}
            page._apply_contango_gain_drop_bonuses()
            for card_id, sign in ((11, 1), (15, -1), (17, 1)):
                with self.subTest(silver=silver, gold=gold, card=card_id):
                    card = restore_card_instance(serialize_card_instance(InvestedCard(card_id, 1)))
                    self.assertEqual(page._get_card_action(card), sign * 3 * factor)
                    self.assertEqual(page._get_card_action(card_id), sign * (4 if silver else 2))
                    self.assertEqual(card.investment_bonus, 1)

    def test_level_price_and_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[442], 5)
        self.assertEqual(CARD_NAMES[442], 'Leverage')
        self.assertEqual(CARD_TOOLTIPS[442], ('Leverage', CARD_DESCRIPTIONS[442]))
        cards = {442: game_state.load_cards_config()[442]}
        self.assertEqual(cards[442], {'Type': 5, 'Open': 1, 'Variable': '1'})
        with mock.patch.object(game_state, 'load_cards_config', return_value=cards):
            with mock.patch.object(game_state.random, 'randint', return_value=1) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(6), [442])
                self.assertEqual(game_state.build_gold_cards_pool(8), [442])
            with mock.patch.object(game_state.random, 'randint', return_value=2):
                self.assertEqual(game_state.build_gold_cards_pool(6), [])
