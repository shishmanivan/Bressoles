import unittest
from unittest import mock

from gameplay_page import GameplayPage
from silver_black_page import SilverBlackPage


def make_page():
    page = GameplayPage.__new__(GameplayPage)
    page.card_types = {1: 1, 11: 1, 100: 2, 125: 2, 408: 5, 415: 5, 428: 5}
    page.boss_market_slots_per_market = 3
    page.market_cards = {market: {slot: None for slot in range(3)} for market in range(3)}
    page.market_cards_locked = {market: {} for market in range(3)}
    page.side_cards_top = [None] * 6
    page.side_cards_locked_top = {}
    page.boss_limit_red_gain_drop_per_turn = False
    page.Day = 1
    page.LastTurn = 8
    page.active_lifecycle_card_order = []
    page.active_silver_cards = []
    page.active_black_cards = []
    page.active_gold_cards = []
    page.hedger_used_this_round = 0
    page.surge_triggered = False
    page.full_deployment_reward_applied = False
    page.hand_negative_overlay_hold = {"red": False, "market": False}
    page.round_num = 1
    page.is_boss_fight = False
    return page


class HandCardAvailabilityTests(unittest.TestCase):
    def test_full_markets_do_not_mark_cards_as_broken(self):
        page = make_page()
        for cards in page.market_cards.values():
            for slot in cards:
                cards[slot] = 1

        self.assertFalse(page._should_show_hand_card_negative(1))

    def test_breakout_is_never_marked_as_broken(self):
        page = make_page()

        self.assertFalse(page._should_show_hand_card_negative(125))
        page.Day = page.LastTurn - 1
        self.assertFalse(page._should_show_hand_card_negative(125))

    def test_red_card_is_broken_only_when_the_play_limit_is_reached(self):
        page = make_page()
        page.boss_limit_red_gain_drop_per_turn = True
        page.side_cards_top[0] = 100

        self.assertTrue(page._should_show_hand_card_negative(100))

    def test_markers_remain_until_the_next_turn_starts(self):
        page = make_page()
        page.boss_limit_red_gain_drop_per_turn = True
        page.side_cards_top[0] = 100

        page._hold_hand_negative_overlays_until_next_turn()
        page.side_cards_locked_top[0] = True

        self.assertTrue(page._should_show_hand_card_negative(100))
        page._clear_hand_negative_overlay_hold()
        self.assertFalse(page._should_show_hand_card_negative(100))

    def test_market_limit_marker_does_not_clear_when_market_cards_lock_early(self):
        page = make_page()
        page.boss_limit_red_gain_drop_per_turn = True
        page.market_cards[0][0] = 11

        page._hold_hand_negative_overlays_until_next_turn()
        page.market_cards_locked[0][0] = True

        self.assertTrue(page._should_show_hand_card_negative(11))
        page._clear_hand_negative_overlay_hold()
        self.assertFalse(page._should_show_hand_card_negative(11))


class ExhaustedLifecycleCardTests(unittest.TestCase):
    def test_golden_stocks_is_broken_after_triggering(self):
        page = make_page()
        with mock.patch("gameplay_page.game_state.is_golden_stocks_triggered", return_value=True):
            self.assertTrue(page._is_lifecycle_card_power_lost(302))

    def test_one_shot_lifecycle_cards_are_broken_after_use(self):
        page = make_page()
        page.surge_triggered = True
        page.full_deployment_reward_applied = True

        self.assertTrue(page._is_lifecycle_card_power_lost(415))
        self.assertTrue(page._is_lifecycle_card_power_lost(428))

    def test_used_hedger_copies_are_marked_individually(self):
        page = make_page()
        page.active_lifecycle_card_order = [
            {"kind": "gold", "card_id": 408},
            {"kind": "gold", "card_id": 408},
        ]
        page.hedger_used_this_round = 1

        self.assertTrue(page._is_lifecycle_card_power_lost(408, slot=0))
        self.assertFalse(page._is_lifecycle_card_power_lost(408, slot=1))


class StorageOverlayTests(unittest.TestCase):
    @staticmethod
    def _page(round_number=None, is_boss_fight=False):
        page = SilverBlackPage.__new__(SilverBlackPage)
        page.round_number = round_number
        page.is_boss_fight = is_boss_fight
        return page

    def test_triggered_golden_stocks_is_broken_in_storage_immediately(self):
        page = self._page(round_number=1)
        with mock.patch("silver_black_page.game_state.is_golden_stocks_triggered", return_value=True):
            self.assertTrue(page._should_show_negative_overlay(302))

    def test_other_storage_cards_are_not_affected(self):
        page = self._page(round_number=1)
        with mock.patch("silver_black_page.game_state.is_golden_stocks_triggered", return_value=True):
            self.assertFalse(page._should_show_negative_overlay(301))

    def test_markdown_is_broken_outside_rounds_three_and_four(self):
        for round_number, expected in ((1, True), (2, True), (3, False), (4, False), (5, True)):
            with self.subTest(round_number=round_number):
                page = self._page(round_number=round_number)
                self.assertEqual(page._should_show_negative_overlay(422), expected)

    def test_markdown_is_broken_before_a_boss_even_if_round_number_is_eligible(self):
        page = self._page(round_number=3, is_boss_fight=True)
        self.assertTrue(page._should_show_negative_overlay(422))

    def test_markdown_is_also_broken_on_the_game_field_when_ineffective(self):
        page = make_page()
        page.round_num = 2
        self.assertTrue(page._is_lifecycle_card_power_lost(422))
        page.round_num = 3
        self.assertFalse(page._is_lifecycle_card_power_lost(422))


if __name__ == "__main__":
    unittest.main()
