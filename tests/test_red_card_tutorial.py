import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import profile_manager
from game_data import load_cards_config
from gameplay_page import GameplayPage
from gameplay_tutorial import RED_CARD_HINT_ID


class RedCardTutorialTests(unittest.TestCase):
    def test_only_red_cards_in_hand_trigger_after_dealing_and_respect_profile_choice(self):
        page = GameplayPage.__new__(GameplayPage)
        page.test_mode = False
        page.profile_slot = 1
        page.tutorial_hint = None
        page.tutorial_dismissed_this_round = set()
        page.win_lose_state = None
        page.pause_menu_active = page.deck_view_active = False
        page._is_turn_resolution_active = mock.Mock(return_value=False)
        page._is_hand_transition_active = mock.Mock(return_value=False)
        page.card_types = {card: config["Type"] for card, config in load_cards_config().items()}
        self.assertEqual(page.card_types[100], 2)  # Shareholder uses the same play area, but is not red.
        page.screen = mock.Mock()
        page.frame = page.font_path = page.ok1_button = None
        page.hand_cards = [None, 1, 100]
        page.deck = [110]
        page.side_cards_top = [110]
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            profile_manager, "PROFILES_DIR", directory
        ), mock.patch("gameplay_page.TutorialHint") as factory:
            page._maybe_show_red_card_tutorial()
            factory.assert_not_called()
            page.hand_cards.append(110)
            page._is_hand_transition_active.return_value = True
            page._maybe_show_red_card_tutorial()
            factory.assert_not_called()
            page._is_hand_transition_active.return_value = False
            page._maybe_show_red_card_tutorial()
            factory.assert_called_once()
            self.assertEqual(factory.call_args.kwargs["hint_id"], RED_CARD_HINT_ID)
            page._maybe_show_red_card_tutorial()
            factory.assert_called_once()
            page.tutorial_hint = None
            profile_manager.mark_tutorial_seen(1, RED_CARD_HINT_ID)
            factory.reset_mock()
            page._maybe_show_red_card_tutorial()
            factory.assert_not_called()
            page.profile_slot = 2
            page.tutorial_dismissed_this_round.clear()
            page._maybe_show_red_card_tutorial()
            factory.assert_called_once()
