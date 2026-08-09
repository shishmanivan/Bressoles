import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from gameplay_deck import deal_starting_hand, setup_starting_deck_and_hand
from gameplay_drag import find_market_drag_start, find_side_top_drag_start
from gameplay_page import GameplayPage


class StartingHandTests(unittest.TestCase):
    def test_guaranteed_cards_that_do_not_fit_remain_in_the_deck(self):
        with mock.patch("gameplay_deck.random.shuffle"):
            remaining, hand = deal_starting_hand(
                [110, 111, 112, 1],
                hand_size=1,
                guaranteed_cards=[110, 111, 112],
            )

        self.assertEqual(hand, [110])
        self.assertEqual(remaining, [111, 112, 1])
        self.assertCountEqual(remaining + hand, [110, 111, 112, 1])

    def test_zero_size_hand_does_not_consume_guaranteed_cards(self):
        with mock.patch("gameplay_deck.random.shuffle"):
            remaining, hand = deal_starting_hand([110, 1], 0, [110])

        self.assertEqual(hand, [])
        self.assertEqual(remaining, [110, 1])

    def test_positioning_cards_take_priority_in_the_starting_hand(self):
        with mock.patch("gameplay_deck.random.shuffle"):
            remaining, hand = setup_starting_deck_and_hand(
                level_number=1,
                hand_size=3,
                earned_reward_cards={1: [112]},
                guaranteed_cards_by_level={1: [112]},
                round_guaranteed_cards=[3, 4],
            )

        self.assertEqual(hand, [3, 4, 112])
        self.assertNotIn(112, remaining)


class HandDrawTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.hand = 4
        page.Dobor = 2
        page.deck = []
        page.hand_cards = [1, None, 2, None]
        page.pending_draws = 2
        page.bottom_frame = None
        page.hand_compact_anim = []
        page.hand_compact_target_hand = None
        page.hand_compact_draw_count = 0
        page.hand_draw_anim = []
        return page

    def test_instant_draw_compacts_hand_and_preserves_card_count(self):
        page = self._page()
        page.deck = [3, 4, 11]
        before_cards = list(page.deck) + [card for card in page.hand_cards if card is not None]

        page._draw_pending_cards()

        self.assertEqual(page.hand_cards, [1, 2, 3, 4])
        self.assertEqual(page.deck, [11])
        self.assertEqual(page.pending_draws, 0)
        self.assertCountEqual(
            page.deck + [card for card in page.hand_cards if card is not None],
            before_cards,
        )

    def test_empty_deck_still_clears_pending_draw_counter(self):
        page = self._page()

        page._draw_pending_cards()

        self.assertEqual(page.hand_cards, [1, 2, None, None])
        self.assertEqual(page.pending_draws, 0)

    def test_animated_compaction_and_draw_preserve_every_card(self):
        page = self._page()
        page.bottom_frame = pygame.Surface((900, 300))
        page.deck = [3, 4]
        page.hand_compact_duration = 1
        page.hand_draw_duration = 1
        page._save_active_game = mock.Mock()
        before_cards = list(page.deck) + [card for card in page.hand_cards if card is not None]

        with mock.patch.object(pygame.time, "get_ticks", return_value=0):
            page._draw_pending_cards()

        self.assertTrue(page.hand_compact_anim)
        self.assertEqual(page.deck, [3, 4])

        with mock.patch.object(pygame.time, "get_ticks", return_value=2):
            page.update_hand_compact_animation()

        self.assertEqual(page.hand_cards, [1, 2, None, None])
        self.assertEqual(page.deck, [])
        self.assertEqual([entry["card_id"] for entry in page.hand_draw_anim], [3, 4])

        with mock.patch.object(pygame.time, "get_ticks", return_value=4):
            page.update_hand_draw_animation()

        self.assertEqual(page.hand_cards, [1, 2, 3, 4])
        self.assertEqual(page.deck, [])
        self.assertCountEqual(page.hand_cards, before_cards)

    def test_terminal_rebate_resolution_does_not_draw_more_cards(self):
        page = GameplayPage.__new__(GameplayPage)
        page.turn_resolution_active = True
        page.win_lose_state = "win"
        page.pending_draws = 2
        page.red_effects_applied_this_resolution = True
        page.hand_compact_anim = []
        page.hand_draw_anim = []
        page._draw_pending_cards = mock.Mock()
        page._save_active_game = mock.Mock()

        page._finish_deferred_turn_resolution_after_final_liquidation()

        self.assertEqual(page.pending_draws, 0)
        self.assertFalse(page.turn_resolution_active)
        page._draw_pending_cards.assert_not_called()
        page._save_active_game.assert_called_once_with()


class HandInteractionLockTests(unittest.TestCase):
    def test_mouse_input_is_ignored_during_hand_compaction(self):
        page = GameplayPage.__new__(GameplayPage)
        page.pause_menu_active = False
        page.deck_view_active = False
        page.win_lose_state = None
        page.win_lose_image = None
        page.hand_compact_anim = [{"progress": 0.5}]
        page.hand_draw_anim = []
        page._is_final_auto_liquidation_animating = mock.Mock(return_value=False)
        page._start_card_drag = mock.Mock()

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, 10)})
        with (
            mock.patch.object(pygame.event, "get", return_value=[event]),
            mock.patch.object(pygame.mouse, "get_pos", return_value=(10, 10)),
        ):
            page.handle_input()

        page._start_card_drag.assert_not_called()

    def test_hand_becomes_interactive_after_transition_finishes(self):
        page = GameplayPage.__new__(GameplayPage)
        page.hand_compact_anim = []
        page.hand_draw_anim = []

        self.assertFalse(page._is_hand_transition_active())

    def test_result_window_absorbs_clicks_outside_its_button(self):
        page = GameplayPage.__new__(GameplayPage)
        page.pause_menu_active = False
        page.deck_view_active = False
        page.win_lose_state = "win"
        page.win_lose_image = pygame.Surface((200, 200))
        page.ok1_button = pygame.Surface((40, 40))
        page.ok2_button = None
        page.ok_button_rect = pygame.Rect(150, 150, 40, 40)
        page.ok_button_base_size = (40, 40)
        page.win_lose_x = 0
        page.win_lose_y = 0
        page.hand_compact_anim = []
        page.hand_draw_anim = []
        page._start_card_drag = mock.Mock()

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, 10)})
        with (
            mock.patch.object(pygame.event, "get", return_value=[event]),
            mock.patch.object(pygame.mouse, "get_pos", return_value=(10, 10)),
        ):
            page.handle_input()

        page._start_card_drag.assert_not_called()


class PlayedCardDragTests(unittest.TestCase):
    def test_only_last_unlocked_market_card_can_be_picked_up(self):
        placeholders = [
            {"market": 0, "slot": 0, "rect": pygame.Rect(0, 0, 20, 20)},
            {"market": 0, "slot": 1, "rect": pygame.Rect(30, 0, 20, 20)},
        ]
        cards = {0: {0: 1, 1: 2}, 1: {}, 2: {}}
        locked = {0: {0: False, 1: False}, 1: {}, 2: {}}

        self.assertIsNone(find_market_drag_start((10, 10), placeholders, cards, locked))
        self.assertEqual(
            find_market_drag_start((40, 10), placeholders, cards, locked)["dragged_card_market_slot"],
            1,
        )

        locked[0][1] = True
        self.assertIsNone(find_market_drag_start((40, 10), placeholders, cards, locked))

    def test_only_last_unlocked_side_card_can_be_picked_up(self):
        placeholders = [
            {"slot": 0, "rect": pygame.Rect(0, 0, 20, 20)},
            {"slot": 1, "rect": pygame.Rect(30, 0, 20, 20)},
        ]
        cards = [100, 110, None, None, None, None]
        locked = {0: False, 1: False}

        self.assertIsNone(find_side_top_drag_start((10, 10), placeholders, cards, locked))
        self.assertEqual(
            find_side_top_drag_start((40, 10), placeholders, cards, locked)["dragged_card_side_slot"],
            1,
        )

        locked[1] = True
        self.assertIsNone(find_side_top_drag_start((40, 10), placeholders, cards, locked))


if __name__ == "__main__":
    unittest.main()
