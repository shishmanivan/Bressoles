import unittest
from unittest import mock

import game_state
import localization
from gameplay_price_helpers import build_stock_price_animation_queue
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS
from tests import test_lifecycle_effects


class StandardizationTests(unittest.TestCase):
    def test_fixed_steps_with_duplicates_and_volatility(self):
        for gold in ([440], [440, 440], [424, 440], [440, 425], [424, 425, 440]):
            with self.subTest(gold=gold):
                page = test_lifecycle_effects.LifecycleEffectTests._page(gold=gold)
                page.StepA, page.StepB, page.StepC = 2, 4, 6
                page._apply_volatility_steps()
                steps = (page.StepA, page.StepB, page.StepC)
                self.assertEqual(steps, (4, 4, 4))
                for direction, expected in (("rise", 4), ("fall", -4)):
                    queue = build_stock_price_animation_queue(
                        *steps, **{f"forced_{direction}_markets": [0, 1, 2]}
                    )
                    self.assertEqual([entry["price_change"] for entry in queue], [expected] * 3)

    def test_inactive_card_preserves_default_steps(self):
        page = test_lifecycle_effects.LifecycleEffectTests._page()
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page._apply_volatility_steps()
        self.assertEqual((page.StepA, page.StepB, page.StepC), (2, 4, 6))

    def test_catalog_price_level_chance_and_translations(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[440], 4)
        self.assertEqual(CARD_NAMES[440], "Standardization")
        cards = {440: game_state.load_cards_config()[440]}
        self.assertEqual(cards[440], {"Type": 5, "Open": 1, "Variable": "20"})
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=20) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(5), [440])
            with mock.patch.object(game_state.random, "randint", return_value=21):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
            self.assertNotIn(440, game_state.build_all_available_shop_cards(4))
            self.assertIn(440, game_state.build_all_available_shop_cards(5))
        description = CARD_DESCRIPTIONS[440]
        self.assertEqual(CARD_TOOLTIPS[440], ("Standardization", description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertIn("Standardization", catalog)
            self.assertIn("4", catalog[description])
            if language != "RU":
                self.assertNotEqual(catalog[description], description)
