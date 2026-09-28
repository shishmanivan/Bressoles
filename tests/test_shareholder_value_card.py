import unittest
from unittest import mock

import game_state
import localization
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS
from tests.test_red_card_effects import RedCardEffectTests


class ShareholderValueTests(unittest.TestCase):
    def page(self, gold=(439,), shareholders=1):
        page = RedCardEffectTests._page()
        page.active_gold_cards = list(gold)
        page.side_cards_top[:shareholders] = [100] * shareholders
        page.lifecycle_card_jump_animations = {}
        page.Money = 10
        return page

    def test_each_shareholder_and_each_active_copy_pays(self):
        for copies, shareholders in [(1, 1), (1, 3), (2, 1), (2, 3)]:
            with self.subTest(copies=copies, shareholders=shareholders):
                page = self.page((439,) * copies, shareholders)
                page._apply_shareholder_value_effect_if_needed()
                self.assertEqual(page.Money, 10 + 2 * copies * shareholders)
                self.assertEqual(len(page.lifecycle_card_jump_animations), copies)
                self.assertEqual(len(page.side_card_jump_animations), shareholders)

    def test_only_fresh_played_shareholders_pay(self):
        page = self.page(shareholders=2)
        page.side_cards_locked_top[0] = True
        page.hand_cards = [100, 100]
        page.side_cards_top[2] = 110
        page._apply_shareholder_value_effect_if_needed()
        self.assertEqual(page.Money, 12)
        page._lock_side_cards()
        self.assertFalse(page._apply_shareholder_value_effect_if_needed())
        self.assertEqual(page.Money, 12)
        page.side_cards_top[3] = 100
        page._apply_shareholder_value_effect_if_needed()
        self.assertEqual(page.Money, 14)

    def test_no_payout_without_active_card_or_played_shareholder(self):
        for page in (self.page(gold=()), self.page(shareholders=0)):
            self.assertFalse(page._apply_shareholder_value_effect_if_needed())
            self.assertEqual(page.Money, 10)

    def test_resolution_waits_for_animation_without_repeating_payout(self):
        page = self.page((439, 439), 2)
        page.boss_block_card_turn_extensions = True
        page.turn_resolution_active = True
        page.red_effects_applied_this_resolution = False
        page._has_effect_animations = lambda: True
        page._begin_effect_finalize_or_wait()
        page._begin_effect_finalize_or_wait()
        self.assertEqual(page.Money, 18)
        self.assertTrue(page.red_effects_applied_this_resolution)

    def test_catalog_price_level_chance_and_translations(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[439], 5)
        self.assertEqual(CARD_NAMES[439], "Shareholder Value")
        cards = {439: game_state.load_cards_config()[439]}
        self.assertEqual(cards[439], {"Type": 5, "Open": 1, "Variable": "7"})
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=7) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(6), [439])
            with mock.patch.object(game_state.random, "randint", return_value=8):
                self.assertEqual(game_state.build_gold_cards_pool(6), [])
            self.assertNotIn(439, game_state.build_all_available_shop_cards(5))
            self.assertIn(439, game_state.build_all_available_shop_cards(6))
        description = CARD_DESCRIPTIONS[439]
        self.assertEqual(CARD_TOOLTIPS[439], ("Shareholder Value", description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertIn("Shareholder", catalog[description])
            if language != "RU":
                self.assertNotEqual(catalog[description], description)
