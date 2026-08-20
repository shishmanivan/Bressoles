import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from gameplay_page import GameplayPage


class RedCardEffectTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.boss_limit_red_gain_drop_per_turn = False
        page.side_cards_top = [None] * 6
        page.side_cards_locked_top = {}
        page.card_types = {100: 2, **{card_id: 2 for card_id in range(110, 127)}}
        page.active_silver_cards = []
        page.active_black_cards = []
        page.active_gold_cards = []
        page.active_lifecycle_card_order = []
        page.side_card_jump_animations = {}
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.market_card_origins = {0: {}, 1: {}, 2: {}}
        page.market_cards_locked = {0: {}, 1: {}, 2: {}}
        page.market_card_turns = {0: {}, 1: {}, 2: {}}
        page.market_card_actions = {0: {}, 1: {}, 2: {}}
        page.accumulation_pending_sources = []
        page.card_actions = {}
        page.card_turns = {}
        page.price_card_queue = []
        page.current_card_processing = None
        page.c_price_fell_this_resolution = False
        return page

    def test_stephenson_counts_shareholder_toward_the_side_field_limit(self):
        page = self._page()
        page.boss_limit_red_gain_drop_per_turn = True
        page.side_cards_top[0] = 100
        page.side_cards_locked_top[0] = False

        self.assertFalse(page._can_play_dragged_hand_card_on_side_top(110))

        page.side_cards_locked_top[0] = True
        page.side_cards_top[1] = 110
        page.side_cards_locked_top[1] = False
        self.assertFalse(page._can_play_dragged_hand_card_on_side_top(100))
        self.assertFalse(page._can_play_dragged_hand_card_on_side_top(111))

        page.side_cards_locked_top[1] = True
        self.assertTrue(page._can_play_dragged_hand_card_on_side_top(100))

    def test_stephenson_shares_market_limit_between_gain_drop_and_regulation(self):
        page = self._page()
        page.boss_limit_red_gain_drop_per_turn = True
        page.market_cards[0][0] = 20
        page.market_cards_locked[0][0] = False

        self.assertFalse(page._can_play_dragged_hand_card_on_market(11))
        self.assertFalse(page._can_play_dragged_hand_card_on_market(21))
        self.assertFalse(page._can_play_dragged_hand_card_on_market(22))
        self.assertTrue(page._can_play_dragged_hand_card_on_market(1))

        page.market_cards_locked[0][0] = True
        page.market_cards[1][0] = 11
        page.market_cards_locked[1][0] = False

        self.assertFalse(page._can_play_dragged_hand_card_on_market(20))

        page.market_cards_locked[1][0] = True
        self.assertTrue(page._can_play_dragged_hand_card_on_market(20))

    def test_rollover_adds_a_future_turn_after_current_price_card_processing(self):
        page = self._page()
        page.side_cards_top[0] = 112
        page.side_cards_locked_top[0] = False
        page.card_turns = {11: 1}
        page.card_actions = {11: 2}
        page.market_cards[0][0] = 11
        page.market_card_turns[0][0] = 1
        page.card_processing_start_time = 0
        page.card_processing_delay = 0
        page.Aprice = page.BPrice = page.CPrice = 2
        page._begin_effect_finalize_or_wait = mock.Mock()

        page._queue_price_cards()
        page.update_price_card_processing()

        self.assertEqual(page.Aprice, 4)
        self.assertEqual(page.market_card_turns[0][0], 0)
        self.assertIsNone(page.current_card_processing)
        self.assertEqual(page.price_card_queue, [])

        page._apply_red_card_effects_if_needed()

        self.assertEqual(page.card_turns[11], 2)
        self.assertEqual(page.market_card_turns[0][0], 1)
        self.assertIsNone(page.current_card_processing)
        self.assertEqual(page.price_card_queue, [])

    def test_rollover_extends_both_regulation_cards_in_deck_and_in_play(self):
        page = self._page()
        page.side_cards_top[0] = 112
        page.side_cards_locked_top[0] = False
        page.card_turns = {20: 2, 21: 3}
        page.market_cards[0][0] = 20
        page.market_cards[1][0] = 21
        page.market_card_turns[0][0] = 1
        page.market_card_turns[1][0] = 2

        self.assertTrue(page._apply_extended_gain_drop_effect_if_needed())

        self.assertEqual(page.card_turns[20], 3)
        self.assertEqual(page.card_turns[21], 4)
        self.assertEqual(page.market_card_turns[0][0], 2)
        self.assertEqual(page.market_card_turns[1][0], 3)

    def test_price_card_keeps_occupying_market_slot_after_its_final_jump(self):
        page = self._page()
        page.card_turns = {11: 1}
        page.card_actions = {11: 2}
        page.market_cards[0][0] = 11
        page.market_card_origins[0][0] = 3
        page.market_cards_locked[0][0] = True
        page.market_card_turns[0][0] = 1
        page.current_card_processing = (0, 0)
        page.card_processing_start_time = 0
        page.card_processing_delay = 0
        page.Aprice = page.BPrice = page.CPrice = 2
        page._begin_effect_finalize_or_wait = mock.Mock()

        page.update_price_card_processing()
        animation = page.card_jump_animations[0][0]
        animation.update({"offset_y": 1.0, "velocity": 1.0, "start_time": 0})
        page.update_card_jump_animations()

        self.assertEqual(page.market_cards[0][0], 11)
        self.assertEqual(page.market_card_origins[0][0], 3)
        self.assertTrue(page.market_cards_locked[0][0])
        self.assertEqual(page.market_card_turns[0][0], 0)

    def test_zero_turn_card_stays_in_place_and_is_not_queued(self):
        page = self._page()
        page.card_turns = {11: 1}
        page.market_cards[1][0] = 11
        page.market_cards_locked[1][0] = True
        page.market_card_turns[1][0] = 0

        page._queue_price_cards()

        self.assertEqual(page.market_cards[1][0], 11)
        self.assertTrue(page.market_cards_locked[1][0])
        self.assertEqual(page.market_card_turns[1][0], 0)
        self.assertIsNone(page.current_card_processing)

    def test_bankruptcy_extension_crash_and_deleverage_effects(self):
        page = self._page()
        page.side_cards_top[:5] = [113, 114, 115, 116, 117]
        page.side_cards_locked_top = {slot: False for slot in range(5)}
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page.LastTurn = 8
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_bankruptcy_effects_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (2, 2, 2))
        self.assertTrue(page._apply_extra_turn_effect_if_needed())
        self.assertEqual(page.LastTurn, 9)

        page.Aprice, page.BPrice, page.CPrice = 8, 12, 16
        self.assertTrue(page._apply_market_crash_effect_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (2, 2, 2))

        page.side_cards_top = [111, None, None, None, None, None]
        page.side_cards_locked_top = {0: False}
        page.market_cards = {0: {0: 11}, 1: {0: 12}, 2: {0: 15}}
        page.market_card_origins = {0: {0: 1}, 1: {0: 2}, 2: {0: 3}}
        page.market_cards_locked = {0: {0: True}, 1: {0: True}, 2: {0: True}}
        page.market_card_turns = {0: {0: 1}, 1: {0: 1}, 2: {0: 1}}
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        page.price_card_queue = []
        page.current_card_processing = None
        page._start_market_clear_animation = mock.Mock()

        self.assertTrue(page._apply_deleverage_effect_if_needed())
        self.assertTrue(all(card is None for market in page.market_cards.values() for card in market.values()))

    def test_bid_sets_all_stock_prices_to_its_value(self):
        page = self._page()
        page.side_cards_top[2] = 120
        page.side_cards_locked_top[2] = False
        page.Aprice, page.BPrice, page.CPrice = 2, 17, 83
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_bid_effect_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (30, 30, 30))
        page._start_card_jump_animation.assert_called_once_with(
            page.side_card_jump_animations,
            2,
        )

    def test_last_fresh_bid_in_slot_order_sets_the_final_price(self):
        page = self._page()
        page.side_cards_top[:3] = [118, 122, 121]
        page.side_cards_locked_top = {0: False, 1: True, 2: False}
        page.Aprice = page.BPrice = page.CPrice = 7
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_bid_effect_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (50, 50, 50))
        self.assertEqual(page._start_card_jump_animation.call_count, 2)

    def test_bid_then_bankruptcy_resolves_strictly_from_left_to_right(self):
        page = self._page()
        page.side_cards_top[:2] = [118, 113]
        page.side_cards_locked_top = {0: False, 1: False}
        page.Aprice = page.BPrice = page.CPrice = 7
        page._start_card_jump_animation = mock.Mock()

        page._apply_red_card_effects_if_needed()

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (2, 10, 10))
        self.assertEqual(
            [call.args[1] for call in page._start_card_jump_animation.call_args_list],
            [0, 1],
        )

    def test_bankruptcy_then_bid_resolves_strictly_from_left_to_right(self):
        page = self._page()
        page.side_cards_top[:2] = [113, 118]
        page.side_cards_locked_top = {0: False, 1: False}
        page.Aprice = page.BPrice = page.CPrice = 7
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_price_setting_red_card_effects_in_slot_order())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 10, 10))
        self.assertEqual(
            [call.args[1] for call in page._start_card_jump_animation.call_args_list],
            [0, 1],
        )

    def test_parity_sets_all_prices_to_the_nearest_whole_average(self):
        page = self._page()
        page.side_cards_top[1] = 123
        page.side_cards_locked_top[1] = False
        page.Aprice, page.BPrice, page.CPrice = 10, 11, 14
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_parity_effect_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (12, 12, 12))
        page._start_card_jump_animation.assert_called_once_with(
            page.side_card_jump_animations,
            1,
        )

    def test_locked_parity_does_not_apply_again_on_later_turns(self):
        page = self._page()
        page.side_cards_top[0] = 123
        page.side_cards_locked_top[0] = True
        page.Aprice, page.BPrice, page.CPrice = 3, 9, 30

        self.assertFalse(page._apply_parity_effect_if_needed())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (3, 9, 30))

    def test_accumulation_waits_and_doubles_the_next_gain_drop_instance(self):
        page = self._page()
        page.side_cards_top[2] = 124
        page.side_cards_locked_top[2] = False
        page.market_cards[1][0] = 12
        page.market_card_turns[1][0] = 2
        page.card_actions = {12: 2}
        page.card_turns = {12: 2}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._activate_accumulation_charge(124, 2))
        page._lock_side_cards()
        self.assertEqual(page.accumulation_pending_sources, [2])
        self.assertTrue(page._consume_accumulation_charge(12, 1, 0))

        self.assertEqual(page.market_card_actions[1][0], 4)
        self.assertEqual(page.market_card_turns[1][0], 4)
        self.assertEqual(page.card_actions[12], 2)
        self.assertEqual(page.card_turns[12], 2)
        self.assertTrue(page.market_cards_locked[1][0])
        self.assertEqual(page.accumulation_pending_sources, [])

    def test_accumulation_does_not_consume_on_non_gain_drop_cards(self):
        page = self._page()
        page.side_cards_top[0] = 124
        page.accumulation_pending_sources = [0]

        self.assertFalse(page._consume_accumulation_charge(1, 0, 0))
        self.assertEqual(page.accumulation_pending_sources, [0])

    def test_breakout_can_be_played_only_on_the_last_playable_turn(self):
        page = self._page()
        page.Day = 1
        page.LastTurn = 8

        self.assertFalse(page._can_play_dragged_hand_card_on_side_top(125))
        page.Day = 6
        self.assertFalse(page._can_play_dragged_hand_card_on_side_top(125))
        page.Day = 7
        self.assertTrue(page._can_play_dragged_hand_card_on_side_top(125))

    def test_breakout_doubles_only_owned_markets_and_uses_catalyst_bonus(self):
        page = self._page()
        page.side_cards_top[0] = 125
        page.side_cards_locked_top[0] = False
        page.active_silver_cards = [210]
        page.Aquantity, page.Bquantity, page.Cquantity = 2, 0, 1
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page._start_card_jump_animation = mock.Mock()

        with mock.patch("gameplay_page.random.randint", return_value=60) as roll:
            self.assertTrue(page._apply_breakout_effect_if_needed())

        roll.assert_called_once_with(1, 100)
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (20, 20, 60))

    def test_breakout_misses_above_catalyst_adjusted_chance(self):
        page = self._page()
        page.side_cards_top[0] = 125
        page.side_cards_locked_top[0] = False
        page.active_silver_cards = [210]
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 1, 1
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page._start_card_jump_animation = mock.Mock()

        with mock.patch("gameplay_page.random.randint", return_value=61):
            self.assertFalse(page._apply_breakout_effect_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 20, 30))

    def test_c_fall_flag_survives_a_later_recovery_in_the_same_turn(self):
        page = self._page()

        self.assertTrue(page._record_c_price_fall(12, 8, "test fall"))
        self.assertFalse(page._record_c_price_fall(8, 14, "test recovery"))
        self.assertTrue(page.c_price_fell_this_resolution)

if __name__ == "__main__":
    unittest.main()
