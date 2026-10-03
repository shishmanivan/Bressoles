import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import profile_manager
from gameplay_page import GameplayPage
from gameplay_tutorial import FIRST_HINT_ID, SELL_HINT_ID, SELL_HINT_TEXT, TutorialHint
from gameplay_tutorial import FIRST_HINT_TEXT
from gameplay_tutorial import LOGO_HINT_ID, LOGO_HINT_TEXT
from gameplay_tutorial import BOSS_CHOICE_HINT_ID, BOSS_CHOICE_HINT_TEXT
from boss_page import BossPage
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate
from asset_loaders import find_font_path_or_exit


class TutorialTests(unittest.TestCase):
    def test_boss_choice_hint_level_gate_and_profile_suppression(self):
        page = BossPage.__new__(BossPage)
        page.profile_slot = 1
        page.test_mode = False
        page.tutorial_hint = None
        page.screen = mock.Mock()
        page.font_path = None
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            profile_manager, "PROFILES_DIR", directory
        ), mock.patch("boss_page.load_scaled_image"), mock.patch("boss_page.TutorialHint") as factory:
            for level in (1, 3, 4, 5):
                page.level_number = level
                page._prepare_tutorial()
                factory.assert_not_called()
            page.level_number = 2
            page._prepare_tutorial()
            factory.assert_called_once()
            hint = factory.return_value
            hint.ready_to_close.return_value = True
            hint.dont_show_again = True
            with mock.patch.object(pygame.event, "get", return_value=[]):
                page.handle_input()
            self.assertFalse(profile_manager.is_tutorial_pending(1, BOSS_CHOICE_HINT_ID))
            factory.reset_mock()
            page._prepare_tutorial()
            factory.assert_not_called()
            page.profile_slot = 2
            page._prepare_tutorial()
            factory.assert_called_once()

    def test_all_hint_texts_follow_selected_language_and_fit_the_panel(self):
        original_language = get_language()
        pygame.font.init()
        try:
            for language in SUPPORTED_LANGUAGES:
                set_language(language)
                for hint_id, text in ((FIRST_HINT_ID, FIRST_HINT_TEXT), (SELL_HINT_ID, SELL_HINT_TEXT),
                                      (LOGO_HINT_ID, LOGO_HINT_TEXT), (BOSS_CHOICE_HINT_ID, BOSS_CHOICE_HINT_TEXT)):
                    with self.subTest(language=language, hint=hint_id):
                        translated = translate(text)
                        label = translate("Больше не показывать")
                        if language != "RU":
                            self.assertNotEqual(translated, text)
                            self.assertNotRegex(translated + label, r"[А-Яа-яЁё]")
                        hint = TutorialHint((1680, 1050), None, find_font_path_or_exit(),
                                            hint_id=hint_id, text=text)
                        self.assertEqual(" ".join(hint.lines), translated)
                        text_bottom = hint.checkbox_row.top if hint.has_checkbox else hint.button.top
                        self.assertLessEqual(len(hint.lines) * (hint.font.get_linesize() + 8),
                                             text_bottom - hint.panel.top - 65)
                        self.assertTrue(hint.panel.contains(hint.checkbox_row))
        finally:
            set_language(original_language)
            pygame.font.quit()

    def test_seen_hint_survives_progress_save_and_is_specific_to_profile(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            profile_manager, "PROFILES_DIR", directory
        ):
            profile_manager.save_profile(profile_manager._default_profile(1))
            self.assertTrue(profile_manager.is_tutorial_pending(1, FIRST_HINT_ID))
            profile_manager.mark_tutorial_seen(1, FIRST_HINT_ID)
            profile_manager.save_progress_from_game_state(1)
            self.assertFalse(profile_manager.is_tutorial_pending(1, FIRST_HINT_ID))
            self.assertTrue(profile_manager.is_tutorial_pending(2, FIRST_HINT_ID))

    def test_legacy_profile_does_not_receive_new_player_hint(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            profile_manager, "PROFILES_DIR", directory
        ):
            profile = profile_manager._default_profile(1)
            del profile["tutorial_seen"]
            with open(profile_manager.get_profile_path(1), "w", encoding="utf-8") as output:
                json.dump(profile, output)
            self.assertFalse(profile_manager.is_tutorial_pending(1, FIRST_HINT_ID))

    def test_modal_consumes_gameplay_events_and_dismissal_batch(self):
        pygame.init()
        try:
            page = GameplayPage.__new__(GameplayPage)
            page.profile_slot = 1
            page.tutorial_dismissed_this_round = set()
            page._save_active_game = mock.Mock()
            page.tutorial_hint = TutorialHint((1680, 1050), None, None)
            # The partial page has no gameplay controls: accessing them would fail.
            with mock.patch.object(pygame.event, "get", return_value=[
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)),
            ]):
                self.assertIsNone(page.handle_input())
            with mock.patch.object(pygame.event, "get", return_value=[
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
            ]), mock.patch.object(profile_manager, "mark_tutorial_seen") as mark:
                self.assertIsNone(page.handle_input())
                self.assertTrue(page.tutorial_hint.pressing)
                mark.assert_not_called()
                page.tutorial_hint.press_until = 0
                self.assertIsNone(page.handle_input())
                mark.assert_called_once_with(1, FIRST_HINT_ID)
                self.assertIsNone(page.tutorial_hint)
        finally:
            pygame.quit()

    def test_sell_hint_waits_for_penultimate_turn_in_any_round_or_level(self):
        page = GameplayPage.__new__(GameplayPage)
        page.side_cards_top = []
        page.test_mode = False
        page.profile_slot = 1
        page.tutorial_hint = None
        page.tutorial_dismissed_this_round = set()
        page.level_number = page.round_num = 1
        page.is_boss_fight = False
        page.Day, page.LastTurn = 6, 8
        page.win_lose_state = None
        page.pause_menu_active = page.deck_view_active = False
        page._is_turn_resolution_active = mock.Mock(return_value=False)
        page._is_hand_transition_active = mock.Mock(return_value=False)
        page.screen = mock.Mock()
        page.frame = page.font_path = page.ok1_button = None
        with mock.patch.object(profile_manager, "is_tutorial_pending", return_value=True), mock.patch(
            "gameplay_page.TutorialHint"
        ) as hint:
            for field, value in (("Day", 6), ("Day", 8), ("win_lose_state", "win"),
                                 ("test_mode", True)):
                page.Day = 7
                original = getattr(page, field)
                setattr(page, field, value)
                page._maybe_show_sell_tutorial()
                hint.assert_not_called()
                setattr(page, field, original)
            page._is_hand_transition_active.return_value = True
            page._maybe_show_sell_tutorial()
            hint.assert_not_called()
            page._is_hand_transition_active.return_value = False
            page.side_cards_top = [None, 110, None]
            with mock.patch.object(profile_manager, "mark_tutorial_seen") as mark:
                page._maybe_show_sell_tutorial()
                hint.assert_not_called()
                mark.assert_not_called()
            self.assertNotIn(SELL_HINT_ID, page.tutorial_dismissed_this_round)
            # Only a played Rebate suppresses the reminder; removal restores it.
            page.side_cards_top = [None, 116, None]
            page.hand_cards = [110]
            page.deck = [110]
            page._maybe_show_sell_tutorial()
            hint.assert_called_once()
            self.assertEqual(hint.call_args.kwargs["hint_id"], SELL_HINT_ID)
            # Early wins must not consume the hint. It can first appear later,
            # including during a boss fight or a round with a different length.
            for level, round_num, boss, last_turn in ((1, 2, False, 8), (1, 3, False, 8),
                                                     (2, 1, False, 10), (2, None, True, 12)):
                hint.reset_mock()
                page.tutorial_hint = None
                page.level_number, page.round_num, page.is_boss_fight = level, round_num, boss
                page.LastTurn, page.Day = last_turn, last_turn - 1
                page._maybe_show_sell_tutorial()
                hint.assert_called_once()
            page.tutorial_hint = None
            hint.reset_mock()
            with mock.patch.object(profile_manager, "is_tutorial_pending", return_value=False):
                page._maybe_show_sell_tutorial()
            hint.assert_not_called()

    def test_logo_reminder_third_turn_and_discovery_persist_across_rounds(self):
        page = GameplayPage.__new__(GameplayPage)
        page.test_mode = False
        page.profile_slot = 1
        page.tutorial_hint = None
        page.tutorial_dismissed_this_round = set()
        page.win_lose_state = page.dragged_card_source = None
        page.pause_menu_active = page.deck_view_active = False
        page._is_turn_resolution_active = mock.Mock(return_value=False)
        page._is_hand_transition_active = mock.Mock(return_value=False)
        page.screen = mock.Mock()
        page.frame = page.font_path = page.ok1_button = None
        page.stock_description_font = mock.Mock()
        page.stock_logo_rects = {0: pygame.Rect(20, 20, 100, 100)}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            profile_manager, "PROFILES_DIR", directory
        ), mock.patch("gameplay_page.TutorialHint") as hint_factory:
            hint_factory.return_value.hint_id = LOGO_HINT_ID
            for day in (1, 2):
                page.Day = day
                page._maybe_show_logo_tutorial()
                hint_factory.assert_not_called()
            page.Day = 3
            page._maybe_show_logo_tutorial()
            hint_factory.assert_called_once()
            with mock.patch.object(pygame.mouse, "get_pos", return_value=(50, 50)), mock.patch(
                "gameplay_page.draw_stock_tooltip"
            ) as draw:
                page._draw_stock_logo_tooltip()
                draw.assert_called_once()
            self.assertIsNone(page.tutorial_hint)
            self.assertFalse(profile_manager.is_tutorial_pending(1, LOGO_HINT_ID))
            page._stock_logo_discovered = False  # Simulate another round/reload.
            hint_factory.reset_mock()
            page._maybe_show_logo_tutorial()
            hint_factory.assert_not_called()
            # A different new profile discovers the logo before turn three.
            page.profile_slot = 2
            page._stock_logo_discovered = False
            page.Day = 1
            with mock.patch.object(pygame.mouse, "get_pos", return_value=(50, 50)), mock.patch(
                "gameplay_page.draw_stock_tooltip"
            ):
                page._draw_stock_logo_tooltip()
            page.Day = 3
            page._maybe_show_logo_tutorial()
            hint_factory.assert_not_called()
            self.assertFalse(profile_manager.is_tutorial_pending(2, LOGO_HINT_ID))

    def test_checkbox_controls_permanent_suppression(self):
        pygame.init()
        try:
            for checked in (False, True):
                page = GameplayPage.__new__(GameplayPage)
                page.profile_slot = 1
                page.tutorial_dismissed_this_round = set()
                page._save_active_game = mock.Mock()
                hint = TutorialHint((1680, 1050), None, None,
                                    hint_id=SELL_HINT_ID, text=SELL_HINT_TEXT)
                page.tutorial_hint = hint
                if checked:
                    self.assertFalse(hint.accepts(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1, pos=hint.checkbox_row.center)))
                    self.assertTrue(hint.dont_show_again)
                with mock.patch.object(pygame.event, "get", return_value=[
                    pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
                ]), mock.patch.object(profile_manager, "mark_tutorial_seen") as mark:
                    page.handle_input()
                    self.assertTrue(page.tutorial_hint.pressing)
                    page.tutorial_hint.press_until = 0
                    page.handle_input()
                    self.assertEqual(mark.call_count, int(checked))
                    self.assertIn(SELL_HINT_ID, page.tutorial_dismissed_this_round)
                    page._save_active_game.assert_called_once()
                self.assertFalse(TutorialHint((1680, 1050), None, None).has_checkbox)
        finally:
            pygame.quit()

    def test_ok_press_is_visible_before_close_and_plays_sound_once(self):
        pygame.font.init()
        try:
            hint = TutorialHint((1680, 1050), None, None)
            sound = mock.Mock()
            with mock.patch.object(pygame.time, "get_ticks", return_value=100):
                hint.start_press(sound)
                hint.start_press(sound)
                self.assertFalse(hint.ready_to_close())
                hint.draw(pygame.Surface((1680, 1050)))
                self.assertEqual(hint.press_until, 210)
                self.assertFalse(hint.ready_to_close())
            with mock.patch.object(pygame.time, "get_ticks", return_value=210):
                self.assertTrue(hint.ready_to_close())
            sound.play.assert_called_once()
            self.assertLess(hint.pressed_image.get_width(), hint.ok_image.get_width())
        finally:
            pygame.font.quit()
