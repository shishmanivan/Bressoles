import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import game_state
import localization
import profile_manager
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS
from tests import test_red_card_effects


class OvervaluationTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.overvaluation_multiplier = 1

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def page(self, gold=(441,), silver=()):
        page = test_red_card_effects.RedCardEffectTests._page()
        page.active_gold_cards = list(gold)
        page.active_silver_cards = list(silver)
        page.Aprice = page.BPrice = page.CPrice = 2
        page.rebate_a_fall_bonus_percent = 0
        page.overvaluation_triggered_this_round = False
        page._overvaluation_ready = True
        return page

    def test_threshold_once_per_round_and_progress_next_round(self):
        page = self.page()
        page.Aprice = 98
        self.assertEqual(game_state.get_overvaluation_multiplier(), 1)
        page._apply_price_change(0, 2)
        self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
        page.Aprice = 10
        page.Aprice = 100
        page.Aprice = 200
        self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
        next_round = self.page()
        next_round.Aprice = 96
        next_round._apply_price_change(0, 6)
        self.assertEqual(game_state.get_overvaluation_multiplier(), 3)

    def test_inactive_and_other_markets_do_not_award_progress(self):
        page = self.page(gold=())
        page.Aprice = 100
        self.assertEqual(game_state.get_overvaluation_multiplier(), 1)
        page = self.page()
        page.BPrice = page.CPrice = 100
        self.assertEqual(game_state.get_overvaluation_multiplier(), 1)

    def test_bid_and_gain_multiplication_trigger_even_if_price_falls_later(self):
        for card_id, start, action in ((122, 2, None), (17, 60, 2)):
            with self.subTest(card_id=card_id):
                game_state.overvaluation_multiplier = 1
                page = self.page()
                page.Aprice = start
                if action is None:
                    page.side_cards_top[0] = card_id
                    page._apply_price_setting_red_card_effects_in_slot_order()
                else:
                    page.market_cards[0][0] = card_id
                    page.market_card_turns[0][0] = 1
                    page.card_actions[card_id] = action
                    page.card_processing_delay = 0
                    page._begin_effect_finalize_or_wait = mock.Mock()
                    page._queue_price_cards()
                    page.update_price_card_processing()
                page.Aprice = 2
                self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
                self.assertTrue(page.overvaluation_triggered_this_round)

    def test_total_rebate_multiplier_and_slot_order(self):
        game_state.overvaluation_multiplier = 2
        game_state.napoleondors = 10
        for order, expected in (((410, 441), 240), ((441, 410), 220)):
            page = self.page(gold=order, silver=(201,))
            self.assertEqual(page._get_current_rebate_sale_percent(), expected)
        page = self.page(gold=(407, 441))
        self.assertEqual(page._get_current_rebate_sale_percent(), 260)
        page = self.page()
        self.assertIsNone(page._get_current_rebate_sale_percent())

    def test_duplicate_cards_add_one_progress_step_and_multiply_in_each_slot(self):
        page = self.page(gold=(441, 441), silver=(201,))
        page.Aprice = 100
        self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
        self.assertEqual(page._get_current_rebate_sale_percent(), 400)

    def test_tooltip_always_shows_current_multiplier(self):
        page = self.page()
        with mock.patch.object(game_state, 'is_disclosure_active', return_value=False):
            for multiplier in (1, 2, 10):
                game_state.overvaluation_multiplier = multiplier
                title, description = page._get_field_card_tooltip_content(441)
                self.assertEqual(title, 'Overvaluation')
                self.assertIn(f'Сейчас {multiplier}', description)

    def test_profile_persistence_legacy_default_and_reset(self):
        game_state.overvaluation_multiplier = 4
        progress = profile_manager._capture_progress()
        game_state.overvaluation_multiplier = 1
        profile_manager.apply_profile_to_game_state({'progress': progress})
        self.assertEqual(game_state.get_overvaluation_multiplier(), 4)
        progress.pop('overvaluation_multiplier')
        profile_manager.apply_profile_to_game_state({'progress': progress})
        self.assertEqual(game_state.get_overvaluation_multiplier(), 1)
        game_state.overvaluation_multiplier = 4
        game_state.clear_gold_cards()
        self.assertEqual(game_state.get_overvaluation_multiplier(), 1)

    def test_catalog_price_level_pool_chance_and_localization(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[441], 6)
        self.assertEqual(CARD_NAMES[441], 'Overvaluation')
        cards = {441: game_state.load_cards_config()[441]}
        self.assertEqual(cards[441], {'Type': 5, 'Open': 1, 'Variable': '3'})
        with mock.patch.object(game_state, 'load_cards_config', return_value=cards):
            with mock.patch.object(game_state.random, 'randint', return_value=3) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(5), [441])
            with mock.patch.object(game_state.random, 'randint', return_value=4):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
            self.assertNotIn(441, game_state.build_all_available_shop_cards(4))
            self.assertIn(441, game_state.build_all_available_shop_cards(5))
        description = CARD_DESCRIPTIONS[441]
        self.assertEqual(CARD_TOOLTIPS[441], ('Overvaluation', description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertIn('100', catalog[description])
            self.assertIn('Overvaluation', catalog)
            self.assertIn('Сейчас {v0}', catalog)

    def test_saved_round_does_not_reaward_and_next_round_can_advance(self):
        import pygame
        import gameplay_page
        from asset_loaders import find_font_path_or_exit
        pygame.init()
        self.addCleanup(pygame.quit)
        screen = pygame.display.set_mode((1680, 1050))
        args = dict(level_number=5, goal=100, test_mode=True, active_gold_cards=[441],
                    active_silver_cards=[201])
        with mock.patch.object(gameplay_page, 'ensure_stats_file'):
            page = gameplay_page.GameplayPage(screen, find_font_path_or_exit(), **args)
            page.Aprice = 100
            saved = page._serialize_gameplay_state()
            self.assertTrue(saved['overvaluation_triggered_this_round'])
            self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
            resumed = gameplay_page.GameplayPage(screen, find_font_path_or_exit(), saved_state=saved, **args)
            self.assertTrue(resumed.overvaluation_triggered_this_round)
            self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
            resumed.Aprice = 10
            resumed.Aprice = 100
            self.assertEqual(game_state.get_overvaluation_multiplier(), 2)
            next_round = gameplay_page.GameplayPage(screen, find_font_path_or_exit(), **args)
            self.assertFalse(next_round.overvaluation_triggered_this_round)
            next_round.Aprice = 102
            self.assertEqual(game_state.get_overvaluation_multiplier(), 3)
            self.assertEqual(next_round._get_current_rebate_sale_percent(), 300)
