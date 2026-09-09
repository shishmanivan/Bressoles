import unittest
from unittest import mock

from gameplay_page import GameplayPage
from gameplay_price_helpers import calculate_price_setting_card_prices
from gameplay_turn import calculate_price_card_prices


class PriceCardCalculationTests(unittest.TestCase):
    def test_bid_values_preserve_protected_prices_and_inputs(self):
        for card_id, target in ((118, 10), (119, 20), (120, 30), (121, 50), (122, 100)):
            with self.subTest(card_id=card_id):
                previous = [2, 17, 83]
                protected = {0, 2}
                self.assertEqual(calculate_price_setting_card_prices(previous, card_id), (target,) * 3)
                self.assertEqual(
                    calculate_price_setting_card_prices(previous, str(card_id), protected),
                    (target, target, max(83, target)),
                )
                self.assertEqual(previous, [2, 17, 83])
                self.assertEqual(protected, {0, 2})

    def test_parity_rounding_includes_protected_markets_before_blocking_falls(self):
        for previous, protected, expected in (
            ((2, 2, 2), set(), (2, 2, 2)),
            ((10, 10, 11), set(), (10, 10, 10)),
            ((10, 11, 11), set(), (11, 11, 11)),
            ((10, 11, 20), {2}, (14, 14, 20)),
            ((10, 11, 20), {0, 1, 2}, (14, 14, 20)),
            ((10**18, 10**18, 10**18 + 2), set(), (10**18 + 1,) * 3),
        ):
            with self.subTest(previous=previous, protected=protected):
                self.assertEqual(calculate_price_setting_card_prices(previous, 123, protected), expected)

    def test_all_gain_drop_cards_on_each_market_with_and_without_protection(self):
        for card_id, action, expected_price in (
            (11, 2, 12), (12, 2, 12), (13, 4, 14), (14, 4, 14),
            (15, -2, 8), (16, -2, 8), (17, 2, 20), (18, 2, 20),
        ):
            for market in (0, 1, 2):
                for protected in (False, True):
                    with self.subTest(card_id=card_id, market=market, protected=protected):
                        previous = [10, 10, 10]
                        protected_markets = {market} if protected else set()
                        result = calculate_price_card_prices(
                            previous, market, card_id, action, protected_markets,
                        )
                        expected = [10, 10, 10]
                        expected[market] = max(10, expected_price) if protected else expected_price
                        self.assertEqual(result, tuple(expected))
                        self.assertEqual(previous, [10, 10, 10])
                        self.assertEqual(protected_markets, {market} if protected else set())

    def test_effective_actions_preserve_floor_zero_and_multiplication_rounding(self):
        for card_id, action, expected in (
            (15, -100, 2), (16, -8, 2), (11, 0, 5), (17, 0, 5),
            (11, 8, 13), (17, 4, 20), (18, 1.5, 7), (17, 0.1, 2),
        ):
            with self.subTest(card_id=card_id, action=action):
                result = calculate_price_card_prices((5, 20, 30), 0, card_id, action, {1, 2})
                self.assertEqual(result, (expected, 20, 30))


class PriceCardProcessingTests(unittest.TestCase):
    @staticmethod
    def _page(card_id=15, market=0, action=-2):
        page = GameplayPage.__new__(GameplayPage)
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.market_card_turns = {0: {}, 1: {}, 2: {}}
        page.market_card_actions = {0: {}, 1: {}, 2: {}}
        page.market_cards[market][0] = card_id
        page.market_card_turns[market][0] = 2
        page.card_actions = {card_id: action}
        page.current_card_processing = (market, 0)
        page.price_card_queue = []
        page.card_processing_start_time = 100
        page.card_processing_delay = 50
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page._record_rebate_a_fall = mock.Mock()
        page._record_c_price_fall = mock.Mock()
        page._record_short_seller_falls = mock.Mock(return_value=False)
        page._start_card_jump_animation = mock.Mock()
        page._begin_effect_finalize_or_wait = mock.Mock()
        return page

    def test_delay_and_slot_action_override_including_zero(self):
        for override, expected in ((None, 8), (-6, 4), (0, 10)):
            with self.subTest(override=override):
                page = self._page()
                if override is not None:
                    page.market_card_actions[0][0] = override
                with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=149):
                    page.update_price_card_processing()
                self.assertEqual(page.Aprice, 10)
                self.assertEqual(page.market_card_turns[0][0], 2)
                page._record_rebate_a_fall.assert_not_called()
                with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=150):
                    page.update_price_card_processing()
                self.assertEqual(page.Aprice, expected)
                self.assertEqual(page.market_card_turns[0][0], 1)
                self.assertEqual(page._start_card_jump_animation.call_count, int(expected != 10))
                page._begin_effect_finalize_or_wait.assert_called_once_with()

    def test_reactions_observe_final_price_before_animation_and_duration_decrement(self):
        for protected in (False, True):
            with self.subTest(protected=protected):
                page = self._page()
                if protected:
                    page.market_cards[0][1] = 22
                events = []

                def capture(name):
                    def callback(*args):
                        events.append((name, page.Aprice, page.market_card_turns[0][0]))
                        return False
                    return callback

                for name, method in (
                    ("rebate", "_record_rebate_a_fall"),
                    ("c_fall", "_record_c_price_fall"),
                    ("short_seller", "_record_short_seller_falls"),
                    ("jump", "_start_card_jump_animation"),
                    ("finalize", "_begin_effect_finalize_or_wait"),
                ):
                    getattr(page, method).side_effect = capture(name)
                with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=150):
                    page.update_price_card_processing()
                price = 10 if protected else 8
                expected = [(name, price, 2) for name in ("rebate", "c_fall", "short_seller")]
                if not protected:
                    expected.append(("jump", price, 2))
                self.assertEqual(events, expected + [("finalize", price, 1)])
                page._record_rebate_a_fall.assert_called_once_with(10, price, "card 15")
                page._record_c_price_fall.assert_called_once_with(30, 30, "card 15")
                page._record_short_seller_falls.assert_called_once_with((10, 20, 30), "card 15")

    def test_short_seller_victory_stops_processing_before_duration_and_next_card(self):
        page = self._page()
        page.active_silver_cards = [211]
        page.active_black_cards = []
        page.active_gold_cards = []
        page.active_lifecycle_card_order = []
        page.is_boss_fight = False
        page.Money = 1
        page.Aquantity, page.Bquantity, page.Cquantity = 5, 0, 0
        page.short_seller_fall_counts = [4, 0, 0]
        page.short_seller_counted_markets_this_resolution = set()
        page.lifecycle_card_jump_animations = {}
        page.price_card_queue = [(1, 0)]
        page.win_lose_state = None
        page._finish_win_lose_result = mock.Mock()
        del page._record_short_seller_falls
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=150):
            page.update_price_card_processing()
        self.assertEqual(page.Aprice, 8)
        self.assertEqual(page.short_seller_fall_counts, [5, 0, 0])
        page._finish_win_lose_result.assert_called_once_with("win", "short_seller")
        self.assertEqual(page.market_card_turns[0][0], 2)
        self.assertIsNone(page.current_card_processing)
        self.assertEqual(page.price_card_queue, [])
        page._begin_effect_finalize_or_wait.assert_not_called()
        # Only the lifecycle card jumps; the processed Drop does not.
        page._start_card_jump_animation.assert_called_once_with(page.lifecycle_card_jump_animations, 0)

    def test_queued_cards_use_the_previous_cards_result(self):
        page = self._page(card_id=11, action=2)
        page.market_cards[0][1] = 17
        page.market_card_turns[0][1] = 1
        page.card_actions[17] = 2
        page.price_card_queue = [(0, 1)]
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=150):
            page.update_price_card_processing()
        self.assertEqual(page.Aprice, 12)
        self.assertEqual(page.current_card_processing, (0, 1))
        page._begin_effect_finalize_or_wait.assert_not_called()
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=200):
            page.update_price_card_processing()
        self.assertEqual(page.Aprice, 24)
        self.assertEqual(page.market_card_turns[0], {0: 1, 1: 0})
        page._begin_effect_finalize_or_wait.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
