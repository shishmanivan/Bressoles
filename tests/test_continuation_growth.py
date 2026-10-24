import unittest
from unittest import mock

from tests import test_red_card_effects


class ContinuationGrowthTests(unittest.TestCase):
    @staticmethod
    def page(gold=(), silver=()):
        page = test_red_card_effects.RedCardEffectTests._page()
        page.active_gold_cards = [419, *gold]
        page.active_silver_cards = list(silver)
        page.Aprice = page.BPrice = page.CPrice = 100
        page.Aquantity = page.Bquantity = page.Cquantity = 1
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.Day = 1
        page.level_number = 1
        page.profile_slot = None
        page.test_mode = True
        page.insider_c_growth_turns_remaining = 2 if 405 in gold else 0
        page.continuation_growth_streaks = [0, 0, 0]
        page.continuation_held_markets_this_turn = {0, 1, 2}
        page.stock_price_turn_results = []
        page.price_animation_queue = []
        page.typewriter_sound = None
        page._start_card_jump_animation = mock.Mock()
        return page

    @staticmethod
    def bonuses(page):
        return {m["market"]: m["price_change"] for m in page._build_continuation_bonus_movements()}

    def test_insider_random_spoofing_four_turn_chain(self):
        page = self.page(gold=[404, 405, 411])
        for day, expected in ((1, {}), (2, {2: 20}), (3, {2: 20}), (4, {2: 20})):
            page.Day = day
            page.stock_price_turn_results = page.update_stock_prices() if day != 3 else [
                {"market": 2, "type": "rise"}
            ]
            self.assertEqual(self.bonuses(page), expected)
            self.assertEqual(page.continuation_growth_streaks[2], day)

    def test_each_forced_momentum_copy_counts(self):
        for card, day, market in ((405, 1, 2), (411, 4, 0), (412, 8, 0)):
            for copies in (1, 2):
                with self.subTest(card=card, copies=copies):
                    page = self.page(gold=[404, card] + [409] * copies)
                    page.Day = day
                    page.stock_price_turn_results = page.update_stock_prices()
                    bonus = self.bonuses(page)
                    self.assertEqual(bonus[market], 20 if copies == 1 else 44)
                    self.assertEqual(page.continuation_growth_streaks[market], 1 + copies)

    def test_duplicate_insider_and_spoofing_are_individual_rises(self):
        for card, day, market in ((405, 1, 2), (411, 4, 0)):
            page = self.page(gold=[404, card, card])
            page.Day = day
            page.stock_price_turn_results = page.update_stock_prices()
            self.assertEqual(self.bonuses(page)[market], 20)
            self.assertEqual(page.continuation_growth_streaks[market], 2)

    def test_advance_and_each_surge_multiplier_count(self):
        page = self.page(gold=[420, 415, 415])
        page.stock_price_turn_results = [{"market": m, "type": "rise"} for m in range(3)]
        with mock.patch("gameplay_page.random.randint", return_value=1):
            page.stock_price_turn_results.extend(page._build_advance_movements())
        page.stock_price_turn_results.append({"market": 0, "type": "rise", "source": "surge"})
        self.assertEqual(self.bonuses(page), {0: 73, 1: 20, 2: 20})
        self.assertEqual(page.continuation_growth_streaks, [4, 2, 2])

    def test_basket_trading_is_included_once_for_each_market(self):
        page = self.page(silver=[206])
        page.stock_price_turn_results = [{"market": m, "type": "rise"} for m in range(3)]
        self.assertTrue(page._apply_basket_trading_if_needed())
        self.assertFalse(page._apply_basket_trading_if_needed())
        self.assertEqual(self.bonuses(page), {0: 20, 1: 20, 2: 20})

    def test_gain_and_market_copy_do_not_count_as_growth(self):
        page = self.page()
        page.continuation_growth_streaks = [1, 1, 1]
        page.market_cards[0][0] = 11
        page.market_card_turns[0][0] = 1
        page.card_actions = {11: 10}
        page.current_card_processing = (0, 0)
        page.card_processing_start_time = page.card_processing_delay = 0
        page._begin_effect_finalize_or_wait = mock.Mock()
        page.update_price_card_processing()
        self.assertTrue(page._apply_market_copy_card(23, 1, 1))
        self.assertEqual((page.Aprice, page.BPrice), (110, 110))
        self.assertEqual(page.stock_price_turn_results, [])
        self.assertEqual(self.bonuses(page), {})

    def test_breakout_bid_and_parity_do_not_count_as_growth(self):
        for card in (118, 119, 120, 121, 122, 123, 125):
            with self.subTest(card=card):
                page = self.page()
                page.Aprice, page.BPrice, page.CPrice = 2, 100, 100
                page.continuation_growth_streaks = [1, 1, 1]
                page.side_cards_top[0] = card
                with mock.patch("gameplay_page.random.randint", return_value=1):
                    page._apply_price_setting_red_card_effects_in_slot_order()
                self.assertGreater(page.Aprice, 2)
                self.assertEqual(page.stock_price_turn_results, [])
                self.assertEqual(self.bonuses(page), {})

    def test_fall_and_flat_interrupt_but_later_rises_start_new_series(self):
        for interruption in ("fall", "unchanged"):
            page = self.page()
            page.continuation_growth_streaks = [5, 0, 0]
            page.stock_price_turn_results = [
                {"market": 0, "type": interruption},
                {"market": 0, "type": "rise", "source": "insider"},
                {"market": 0, "type": "rise", "source": "momentum"},
            ]
            self.assertEqual(self.bonuses(page), {0: 20})
            self.assertEqual(page.continuation_growth_streaks[0], 2)

    def test_red_card_effects_do_not_change_market_growth_series(self):
        page = self.page()
        page.continuation_growth_streaks = [3, 0, 0]
        page.stock_price_turn_results = [{"market": 0, "type": "rise"}]
        page.side_cards_top[:3] = [113, 125, 125]
        with mock.patch("gameplay_page.random.randint", return_value=1):
            page._apply_price_setting_red_card_effects_in_slot_order()
        self.assertEqual(self.bonuses(page)[0], 2)
        self.assertEqual(page.continuation_growth_streaks[0], 4)

    def test_own_bonus_is_excluded_and_unheld_stocks_do_not_qualify(self):
        page = self.page()
        page.continuation_held_markets_this_turn = {0}
        page.stock_price_turn_results = [
            {"market": (0, 1, 2), "type": "rise", "source": "advance"},
            {"market": 0, "type": "rise", "source": "continuation"},
        ]
        self.assertEqual(self.bonuses(page), {})
        self.assertEqual(page.continuation_growth_streaks, [1, 0, 0])

    def test_only_insider_and_momentum_count_after_gain_and_breakout(self):
        page = self.page(gold=[404, 405, 409])
        page.stock_price_turn_results = page.update_stock_prices()
        page.price_animation_queue = list(page.stock_price_turn_results)
        while page.price_animation_queue:
            page._start_next_price_animation(now=100)
        self.assertEqual(page.CPrice, 112)
        page.market_cards[2][0] = 11
        page.market_card_turns[2][0] = 1
        page.card_actions = {11: 10}
        page.current_card_processing = (2, 0)
        page.card_processing_start_time = page.card_processing_delay = 0
        page._begin_effect_finalize_or_wait = mock.Mock()
        page.update_price_card_processing()
        page.side_cards_top[0] = 125
        with mock.patch("gameplay_page.random.randint", return_value=1):
            page._apply_price_setting_red_card_effects_in_slot_order()
        self.assertEqual(page.CPrice, 244)
        bonus = page._build_continuation_bonus_movements()
        self.assertEqual(page.continuation_growth_streaks[2], 2)
        self.assertEqual([m["price_change"] for m in bonus if m["market"] == 2], [49])
        page.price_animation_queue = bonus
        while page.price_animation_queue:
            page._start_next_price_animation(now=100)
        self.assertEqual(page.CPrice, 293)
        self.assertFalse(any(m.get("source") == "continuation" for m in page.stock_price_turn_results))

    def test_ready_pulse_has_one_second_period_and_four_percent_peak(self):
        page = self.page()
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)
        page.continuation_growth_streaks = [1, 0, 0]
        for now, expected in ((0, 1.0), (250, 1.02), (500, 1.04),
                              (750, 1.02), (1000, 1.0), (1500, 1.04)):
            self.assertAlmostEqual(page._get_lifecycle_card_scale(0, now=now), expected)
        self.assertFalse(getattr(page, "lifecycle_card_scale_animations", {}))

    def test_sale_stops_pulse_until_another_held_stock_is_ready(self):
        page = self.page()
        page.continuation_growth_streaks = [2, 0, 0]
        page.Money = 0
        page._is_arrow_disabled = mock.Mock(return_value=False)
        page._blocked_buy_prices = mock.Mock(return_value=set())
        page._check_win_lose = mock.Mock()
        self.assertGreater(page._get_lifecycle_card_scale(0, now=500), 1.0)
        self.assertTrue(page._apply_arrow_trade(0, 2))
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)
        page.continuation_growth_streaks[1] = 1
        self.assertGreater(page._get_lifecycle_card_scale(0, now=500), 1.0)
        page.Bquantity = 0
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)

    def test_flat_stops_pulse_and_resolution_or_game_end_hides_it(self):
        page = self.page()
        page.continuation_growth_streaks = [2, 0, 0]
        page.turn_resolution_active = True
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)
        page.turn_resolution_active = False
        page.win_lose_state = "win"
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)
        page.win_lose_state = None
        page.stock_price_turn_results = [{"market": 0, "type": "unchanged"}]
        page._build_continuation_bonus_movements()
        self.assertEqual(page._get_lifecycle_card_scale(0, now=500), 1.0)

    def test_only_continuation_copies_pulse_and_waterloo_scale_is_preserved(self):
        page = self.page(gold=[419, 430])
        page.continuation_growth_streaks = [1, 0, 0]
        self.assertAlmostEqual(page._get_lifecycle_card_scale(0, now=500), 1.04)
        self.assertAlmostEqual(page._get_lifecycle_card_scale(1, now=500), 1.04)
        self.assertEqual(page._get_lifecycle_card_scale(2, now=500), 1.0)
        page._start_lifecycle_card_scale_animation(2, now=50)
        self.assertAlmostEqual(page._get_lifecycle_card_scale(2, now=500), 1.2)
