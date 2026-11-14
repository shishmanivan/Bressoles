import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import game_state
import profile_manager
from shop_page import ShopPage


class ShopRerollTests(unittest.TestCase):
    def setUp(self):
        self.original = profile_manager._capture_progress()
        self.addCleanup(self.restore)

    def restore(self):
        profile = profile_manager._default_profile(1)
        profile['progress'] = self.original
        profile_manager.apply_profile_to_game_state(profile)

    def page(self):
        page = ShopPage.__new__(ShopPage)
        for key, value in dict(level_number=8, discount_percent=50,
                defeated_count=1, bosses_required=3, rounds_remaining=8,
                profile_slot=None, stats_enabled=False, _next_pending=False,
                _reroll_pending=False, _pending_assortment=None,
                _offer_animation=None).items():
            setattr(page, key, value)
        page.sold_offer_indexes = {0}
        page._purchase_stamps = {123: 10}
        page.offer_image_cache = {}
        page._offer_label_surface_cache = {}
        page._capture_offer_layout = Mock(return_value={})
        page._ensure_price_cut_assistance = Mock()
        page._build_offer_rects = Mock(return_value=[])
        page.next_button_sound = Mock()
        return page

    def test_resource_grants_spending_and_zero(self):
        game_state.shop_rerolls = 0
        self.assertFalse(game_state.spend_shop_reroll())
        self.assertEqual(game_state.add_shop_rerolls(2), 2)
        self.assertTrue(game_state.spend_shop_reroll())
        self.assertEqual(game_state.get_shop_rerolls(), 1)
        for invalid in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                game_state.add_shop_rerolls(invalid)

    def test_profile_round_trip_migration_and_zero(self):
        profile = profile_manager._default_profile(1)
        for amount in (0, 7):
            game_state.shop_rerolls = amount
            profile['progress'] = profile_manager._capture_progress()
            game_state.shop_rerolls = 99
            profile_manager.apply_profile_to_game_state(profile)
            self.assertEqual(game_state.get_shop_rerolls(), amount)
        profile['progress'].pop('shop_rerolls')
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(game_state.get_shop_rerolls(), game_state.STARTING_SHOP_REROLLS)

    def test_reroll_preserves_money_and_purchases_and_passes_context(self):
        page = self.page()
        game_state.shop_rerolls = 2
        game_state.napoleondors = 12
        game_state.shop_deck_cards = [117]
        new_offers = [{'kind': 'card', 'card_id': 118, 'cost': 1}]
        with patch('game_state.generate_shop_offers', return_value=new_offers) as generate:
            self.assertTrue(page._reroll_shop())
        self.assertEqual(game_state.get_shop_rerolls(), 1)
        self.assertEqual(game_state.napoleondors, 12)
        self.assertEqual(game_state.shop_deck_cards, [117])
        self.assertEqual(page.offers, new_offers)
        self.assertFalse(page.sold_offer_indexes)
        self.assertFalse(page._purchase_stamps)
        self.assertEqual(generate.call_args.kwargs, dict(level_number=8,
            discount_percent=50, defeated_count=1, bosses_required=3,
            rounds_remaining=8, advance_shop_cooldown=False, excluded_offer_keys=set(), recent_shop_history=[]))

    def test_click_debounce_and_empty_balance(self):
        page = self.page()
        game_state.shop_rerolls = 1
        self.assertTrue(page._start_reroll())
        self.assertFalse(page._start_reroll())
        page.next_button_sound.play.assert_called_once()
        page._reroll_pending = False
        page._offer_animation = {'started': None}
        self.assertFalse(page._start_reroll())
        game_state.shop_rerolls = 0
        with patch('game_state.generate_shop_offers') as generate:
            self.assertFalse(page._reroll_shop())
            generate.assert_not_called()

    def test_start_grant_survives_defeat_and_does_not_repeat_on_resume(self):
        level = game_state.get_campaign_content_level(6)
        game_state.shop_rerolls = 0
        state = game_state.reset_level_attempt(level)
        self.assertTrue(game_state.grant_level_start_reroll(level, state))
        self.assertEqual(game_state.get_shop_rerolls(), 1)
        self.assertFalse(game_state.grant_level_start_reroll(level, state))
        profile = profile_manager._default_profile(1)
        profile['progress'] = profile_manager._capture_progress()
        profile_manager.apply_profile_to_game_state(profile)
        self.assertFalse(game_state.grant_level_start_reroll(level, game_state.boss_progress[level]))
        game_state.add_shop_rerolls(5)
        state = game_state.reset_level_attempt(level)
        self.assertEqual(game_state.get_shop_rerolls(), 6)
        self.assertTrue(game_state.grant_level_start_reroll(level, state))
        self.assertEqual(game_state.get_shop_rerolls(), 7)
        game_state.shop_rerolls = 10
        state = game_state.reset_level_attempt(level)
        self.assertTrue(game_state.grant_level_start_reroll(level, state))
        self.assertEqual(game_state.get_shop_rerolls(), 10)

    def test_other_levels_and_existing_runs_do_not_receive_start_grant(self):
        game_state.shop_rerolls = 0
        for level in (1, 2, 3, 4, 5, 6, 7):
            self.assertFalse(game_state.grant_level_start_reroll(level, game_state.new_boss_progress_state()))
        self.assertFalse(game_state.grant_level_start_reroll(8, {'run_stats_started': True}))
        self.assertEqual(game_state.get_shop_rerolls(), 0)

    def test_three_assortments_are_excluded_then_oldest_returns(self):
        page = self.page()
        page.offers = [{'kind': 'card', 'card_id': 1}]
        page._shop_history = []
        page._remember_shop()
        game_state.shop_rerolls = 10
        for card in (2, 3, 4, 1):
            with patch('game_state.generate_shop_offers', return_value=[
                    {'kind': 'card', 'card_id': card}]) as generate:
                page._reroll_shop()
            excluded = generate.call_args.kwargs['excluded_offer_keys']
            self.assertEqual('card:1' in excluded, card != 1)
            self.assertNotIn(f'card:{card}', excluded)
        self.assertEqual(page._shop_history, [['card:3'], ['card:4'], ['card:1']])

    def test_generator_excludes_cards_specials_licenses_and_keeps_investment(self):
        excluded = {'card:1', 'special:profit', 'license:201'}
        with patch('game_state.build_shop_card_offer_pool', return_value=[1, 2]), patch(
                'game_state.build_all_available_shop_cards', return_value=[1, 2]), patch(
                'game_state.build_license_offer_pool', return_value=[201, 202]), patch(
                'game_state.random.randint', return_value=1), patch(
                'game_state.is_investment_section_available', return_value=True):
            offers = game_state.generate_shop_offers(8, excluded_offer_keys=excluded)
        self.assertFalse(excluded & {game_state.shop_offer_key(o) for o in offers})
        self.assertTrue(any(o['kind'] == 'investment' for o in offers))

    def test_empty_pool_does_not_spend_reroll(self):
        page = self.page()
        game_state.shop_rerolls = 2
        with patch('game_state.generate_shop_offers', return_value=[{'kind': 'investment'}]):
            self.assertFalse(page._reroll_shop())
        self.assertEqual(game_state.get_shop_rerolls(), 2)

    def test_two_remaining_licenses_alternate_without_empty_slots(self):
        history = [['license:201']]
        for expected in (202, 201, 202, 201):
            excluded = {key for shop in history for key in shop}
            with patch('game_state.build_license_offer_pool', return_value=[201, 202]):
                offers = game_state.generate_shop_offers(8, card_slots=0, special_slots=0,
                    excluded_offer_keys=excluded, recent_shop_history=history)
            licenses = [o['card_id'] for o in offers if o['kind'] == 'license']
            self.assertEqual(licenses, [expected])
            history.append([f'license:{expected}'])
            history = history[-3:]

    def test_shortage_uses_oldest_last_appearance_and_keeps_fresh_choices(self):
        for kind in ('card', 'special', 'license'):
            history = [[f'{kind}:old', f'{kind}:repeated'],
                       [f'{kind}:middle'], [f'{kind}:new', f'{kind}:repeated']]
            pool = game_state._fill_shop_history_shortage(
                ['fresh'], ['fresh', 'old', 'middle', 'new', 'repeated'], kind, 3, history)
            self.assertEqual(pool, ['fresh', 'old', 'middle'])
            # Removed/purchased items in history are never resurrected.
            self.assertEqual(game_state._fill_shop_history_shortage(
                [], ['new'], kind, 2, history), ['new'])

    def test_cards_and_specials_fill_from_oldest_eligible_history(self):
        history = [['card:1', 'special:profit'], ['card:2', 'special:trader'],
                   ['card:3', 'special:delisting']]
        with patch('game_state.build_shop_card_offer_pool', return_value=[1, 2, 3]), patch(
                'game_state.build_all_available_shop_cards', return_value=[1, 2, 3]), patch(
                'game_state.build_shop_special_offer_pool', return_value=[]), patch(
                'game_state._available_screening_offer_ids', return_value=['profit', 'trader', 'delisting']), patch(
                'game_state.is_screening_offer_available', return_value=False):
            offers = game_state.generate_shop_offers(8, card_slots=1, special_slots=1,
                excluded_offer_keys={key for shop in history for key in shop}, recent_shop_history=history)
        self.assertEqual([o['card_id'] for o in offers if o['kind'] == 'card'], [1])
        self.assertEqual([o['special_id'] for o in offers if o['kind'] == 'special'], ['profit'])

    def test_shop_history_survives_profile_save(self):
        game_state.boss_progress[8] = game_state.new_boss_progress_state()
        game_state.boss_progress[8]['shop_history'] = [['card:1'], ['special:profit'], ['license:201']]
        profile = profile_manager._default_profile(1)
        profile['progress'] = profile_manager._capture_progress()
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(game_state.boss_progress[8]['shop_history'],
                         [['card:1'], ['special:profit'], ['license:201']])

    def test_market_refresh_pool_boundaries(self):
        game_state.deal_flow_bonus_percent = 0
        game_state.boss_rare_card_pool_bonus_percent = 0
        for level in (1, 2, 3, 4, 5, 6, 8):
            for balance in (0, 4, 5, 6, 10):
                for roll in (20, 21):
                    game_state.shop_rerolls = balance
                    with patch('game_state.random.randint', return_value=roll), patch(
                            'game_state.get_shop_special_offer_chance', side_effect=lambda chance: chance):
                        pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
                    self.assertEqual('market_refresh' in pool,
                        level >= 6 and balance <= 5 and roll <= 20,
                        (level, balance, roll))
                    available = game_state._available_screening_offer_ids(level)
                    self.assertEqual('market_refresh' in available, level >= 6 and balance <= 5)

    def test_market_refresh_purchase_and_stale_offer(self):
        page = self.page()
        page.offers = [{'kind': 'special', 'special_id': 'market_refresh',
                        'cost': game_state.get_shop_special_cost('market_refresh', 8)}]
        self.assertEqual(page.offers[0]['cost'], 4)
        for balance, money, success in ((5, 4, True), (4, 4, True),
                                        (6, 4, False), (0, 3, False)):
            page.sold_offer_indexes.clear()
            game_state.shop_rerolls = balance
            game_state.napoleondors = money
            page._perform_buy_offer(0)
            self.assertEqual(game_state.get_shop_rerolls(), balance + (5 if success else 0))
            self.assertEqual(game_state.napoleondors, money - (4 if success else 0))
            self.assertEqual(0 in page.sold_offer_indexes, success)
            if success:
                page._perform_buy_offer(0)
                self.assertEqual(game_state.get_shop_rerolls(), balance + 5)

    def test_rerolls_are_hidden_and_blocked_before_level_six(self):
        page = self.page()
        game_state.shop_rerolls = 5
        for level in range(1, 6):
            page.level_number = level
            self.assertFalse(page._start_reroll())
            self.assertFalse(page._reroll_shop())
            # No render attributes exist on this test page: returning early is required.
            page._draw_reroll_button()
        self.assertEqual(game_state.get_shop_rerolls(), 5)

    def test_cap_applies_to_grants_and_loaded_profiles(self):
        game_state.shop_rerolls = 8
        self.assertEqual(game_state.add_shop_rerolls(5), 10)
        profile = profile_manager._default_profile(1)
        profile['progress']['shop_rerolls'] = 999
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(game_state.shop_rerolls, 10)

    def test_reroll_does_not_advance_correction_shop_cooldown(self):
        game_state.correction_shop_cooldown = 2
        with patch('game_state.build_shop_special_offer_pool', return_value=[]):
            game_state.generate_shop_offers(4, advance_shop_cooldown=False)
        self.assertEqual(game_state.correction_shop_cooldown, 2)


if __name__ == '__main__':
    unittest.main()
