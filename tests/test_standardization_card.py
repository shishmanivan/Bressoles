import json
import unittest
from unittest import mock

import game_state
import localization
from gameplay_price_helpers import build_market_probabilities
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS
from tests import test_red_card_effects


class StandardizationTests(unittest.TestCase):
    def page(self, gold=(440,)):
        page = test_red_card_effects.RedCardEffectTests._page()
        page.active_gold_cards = list(gold)
        page.Aprice, page.BPrice, page.CPrice = 18, 30, 50
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.Day = 1
        page.Aquantity = page.Bquantity = page.Cquantity = 1
        page.insider_c_growth_turns_remaining = 0
        page.typewriter_sound = None
        return page

    def test_snapshot_is_once_and_prices_are_independent_afterwards(self):
        page = self.page()
        self.assertTrue(page._apply_standardization_start())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18,) * 3)
        page._apply_price_change(0, 2)
        page._apply_price_change(2, -6)
        self.assertFalse(page._apply_standardization_start())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (20, 18, 12))

    def test_starting_effects_follow_visible_order_instead_of_inventory_order(self):
        for order, expected in (
            ([440, 421], (6, 2, 2)),
            ([421, 440], (6, 6, 6)),
            ([440, 421, 440], (6, 6, 6)),
        ):
            with self.subTest(order=order):
                page = self.page(gold=sorted(order))
                page.active_lifecycle_card_order = page._normalize_active_lifecycle_card_order(
                    [{"kind": "gold", "card_id": card_id} for card_id in order]
                )
                page.Aprice = page.BPrice = page.CPrice = 2
                page._apply_starting_market_effects()
                self.assertEqual((page.Aprice, page.BPrice, page.CPrice), expected)
                page.CPrice = 12
                self.assertFalse(page._apply_starting_market_effects())
                self.assertEqual(page.CPrice, 12)

    def test_starting_effects_do_not_repeat_on_resume(self):
        page = self.page(gold=(421, 440))
        page._initial_saved_state = {"Day": 3}
        self.assertFalse(page._apply_starting_market_effects())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18, 30, 50))

    def test_starting_effects_without_explicit_order_use_equipped_order(self):
        for gold, expected in (((440, 421), (6, 2, 2)), ((421,), (6, 2, 2)), ((440,), (2, 2, 2))):
            with self.subTest(gold=gold):
                page = self.page(gold=gold)
                page.Aprice = page.BPrice = page.CPrice = 2
                page._apply_starting_market_effects()
                self.assertEqual((page.Aprice, page.BPrice, page.CPrice), expected)

    def test_new_cards_on_c_change_only_c_and_a_no_longer_controls_c(self):
        page = self.page()
        page._apply_standardization_start()
        initial = page._stock_bot_probabilities()
        self.assertEqual(initial[0], initial[1])
        self.assertEqual(initial[0], initial[2])
        page.market_cards[2][0] = 4
        changed = page._stock_bot_probabilities()
        self.assertEqual(changed[0], initial[0])
        self.assertEqual(changed[1], initial[1])
        self.assertGreater(changed[2]['fall'], initial[2]['fall'])
        page.market_cards[0][0] = 1
        self.assertEqual(page._stock_bot_probabilities()[2], changed[2])

    def test_regulation_and_gain_on_c_apply_independently(self):
        page = self.page()
        page._apply_standardization_start()
        page.market_cards[2] = {0: 20, 1: 11}
        page.market_card_turns[2] = {0: 2, 1: 1}
        page.card_actions = {11: 2}
        probabilities = page._stock_bot_probabilities()
        self.assertEqual(probabilities[2]['flat'], 100)
        self.assertNotEqual(probabilities[0]['flat'], 100)
        page.card_processing_delay = 0
        page._begin_effect_finalize_or_wait = mock.Mock()
        page._queue_price_cards()
        while page.current_card_processing is not None:
            page.update_price_card_processing()
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18, 18, 20))

    def test_separate_rolls_and_independent_preview_prices(self):
        page = self.page()
        page._apply_standardization_start()
        with mock.patch('gameplay_price_helpers.random.random', side_effect=[0.1, 0.9, 0.9]) as rng:
            queue = page.update_stock_prices()
        self.assertEqual(rng.call_count, 3)
        self.assertEqual([entry['price_change'] for entry in queue], [0, 4, 6])
        self.assertEqual(page._calculate_waterloo_preview_prices(queue), (18, 22, 24))
        page.price_animation_queue = queue
        while page.price_animation_queue:
            page._start_next_price_animation(now=100)
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18, 22, 24))

    def test_save_snapshot_restores_without_copying_prices_again(self):
        page = self.page()
        page._apply_standardization_start()
        state = json.loads(json.dumps({'standardization_probabilities': page.standardization_probabilities}))
        resumed = self.page()
        resumed._restore_standardization_state(state)
        self.assertEqual(resumed.standardization_probabilities, page.standardization_probabilities)
        self.assertFalse(resumed._apply_standardization_start())
        self.assertEqual((resumed.Aprice, resumed.BPrice, resumed.CPrice), (18, 30, 50))
        resumed.market_cards[2][0] = 4
        self.assertGreater(resumed._stock_bot_probabilities()[2]['fall'], 0)

    def test_legacy_save_keeps_current_prices_and_starts_independent_markets(self):
        page = self.page()
        page._restore_standardization_state({})
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18, 30, 50))
        self.assertFalse(page._apply_standardization_start())
        self.assertEqual(page._stock_bot_probabilities()[2], build_market_probabilities()[0])

    def test_inactive_card_and_duplicate_copies(self):
        page = self.page(gold=())
        self.assertFalse(page._apply_standardization_start())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (18, 30, 50))
        self.assertEqual(page._stock_bot_probabilities(), build_market_probabilities())
        page = self.page(gold=(440, 440))
        page._apply_standardization_start()
        page.CPrice = 24
        self.assertFalse(page._apply_standardization_start())
        self.assertEqual(page.CPrice, 24)

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
            for market in ("A", "B", "C"):
                self.assertIn(market, catalog[description])
            if language != "RU":
                self.assertNotEqual(catalog[description], description)
