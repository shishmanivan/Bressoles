import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import localization
from gameplay_page import GameplayPage
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS


class EfficiencyTests(unittest.TestCase):
    def page(self, gold=None, market=None, side=None):
        page = GameplayPage.__new__(GameplayPage)
        page.active_gold_cards = [435] if gold is None else gold
        page.active_silver_cards = []
        page.active_black_cards = []
        page.active_lifecycle_card_order = []
        page.market_cards = {0: dict(enumerate(market or []))}
        page.market_cards_locked = {0: {}}
        page.side_cards_top = list(side or [])
        page.side_cards_locked_top = {}
        page.Day = 1
        page.rebate_a_fall_bonus_percent = 0
        return page

    def test_counts_both_panels_and_ignores_empty_and_old_cards(self):
        for market, side, expected in [([], [], 0), ([11], [], 4),
                                       ([], [110], 4), ([11], [110], 2),
                                       ([11, 15], [110], 0)]:
            with self.subTest(market=market, side=side):
                page = self.page(market=market, side=side)
                page.market_cards[0].update({8: 20, 9: None})
                page.market_cards_locked[0][8] = True
                page.side_cards_locked_top[len(page.side_cards_top)] = True
                page.side_cards_top.extend([111, None])
                self.assertEqual(page._record_efficiency_turn_bonus(), expected)
                self.assertEqual(page.efficiency_bonus_percent, expected)
                self.assertEqual(page._record_efficiency_turn_bonus(), 0)

    def test_accumulates_across_turns_and_duplicate_copies(self):
        page = self.page(gold=[435, 435], market=[11])
        self.assertEqual(page._record_efficiency_turn_bonus(), 8)
        page.Day += 1
        page.side_cards_top = [110]
        self.assertEqual(page._record_efficiency_turn_bonus(), 4)
        self.assertEqual(page.efficiency_bonus_percent, 12)
        page.Day += 1
        page.market_cards_locked[0][0] = True
        page.side_cards_locked_top[0] = True
        self.assertEqual(page._record_efficiency_turn_bonus(), 0)

    def test_bonus_applies_to_all_rebate_bases_but_does_not_enable_rebate(self):
        for gold, silver, side, expected in [([435], [], [], None),
                                            ([435], [], [110], 94),
                                            ([435], [201], [], 104),
                                            ([435, 407], [201], [110], 154)]:
            with self.subTest(gold=gold, silver=silver, side=side):
                page = self.page(gold=gold, market=[11])
                page._record_efficiency_turn_bonus()
                page.active_silver_cards = silver
                page.side_cards_top = side
                self.assertEqual(page._get_current_rebate_sale_percent(), expected)

    def test_absent_efficiency_has_no_effect(self):
        page = self.page(gold=[], market=[11])
        self.assertEqual(page._record_efficiency_turn_bonus(), 0)

    def test_turn_resolution_records_bonus_before_locking_cards(self):
        page = self.page(market=[11])
        page.market_cards.update({1: {}, 2: {}})
        page.market_cards_locked.update({1: {}, 2: {}})
        page._take_waterloo_preview_or_roll = mock.Mock(return_value=[{"market": 0}])
        page._start_next_price_animation = mock.Mock()
        page._start_market_resolution_after_actions()
        self.assertEqual(page.efficiency_bonus_percent, 4)
        self.assertTrue(page.market_cards_locked[0][0])
        page._start_market_resolution_after_actions()
        self.assertEqual(page.efficiency_bonus_percent, 4)

    def test_catalog_price_level_and_probability_boundary(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[435], 5)
        self.assertEqual(CARD_NAMES[435], "Efficiency")
        cards = {435: game_state.load_cards_config()[435]}
        self.assertEqual(cards[435], {"Type": 5, "Open": 1, "Variable": "7"})
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=7) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(6), [435])
            with mock.patch.object(game_state.random, "randint", return_value=8):
                self.assertEqual(game_state.build_gold_cards_pool(6), [])
            self.assertNotIn(435, game_state.build_all_available_shop_cards(5))
            self.assertIn(435, game_state.build_all_available_shop_cards(6))

    def test_description_is_translated_for_every_language(self):
        description = CARD_DESCRIPTIONS[435]
        self.assertEqual(CARD_TOOLTIPS[435], ("Efficiency", description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            translated = catalog[description]
            self.assertRegex(translated, r"4\s*%")
            self.assertRegex(translated, r"2\s*%")
            self.assertIn("Prime de cession" if language == "FR" else "Rebate", translated)
            if language != "RU":
                self.assertNotEqual(translated, description)
