import os
import tempfile
import unittest
from unittest.mock import patch, Mock
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
import profile_manager
from gameplay_tutorial import record_level6_tutorial_result, SIXTH_LEVEL_LOSSES_HINT_TEXT
from settings_page import SettingsPage, ALWAYS_LOSE_LABEL, ALWAYS_LOSE_QUESTIONS
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate
from app_settings import load_settings
from gameplay_page import GameplayPage
from gameplay_tutorial import SIXTH_LEVEL_LOSSES_HINT_ID, TutorialHint
from shared_utils import wrap_text
from start_page import MENU_FONT_PATH


class AlwaysLoseTests(unittest.TestCase):
    def test_setting_unlocks_only_when_hint_is_shown(self):
        page = GameplayPage.__new__(GameplayPage)
        page.profile_slot = 1
        page.screen = Mock()
        page.frame = page.font_path = page.ok1_button = None
        page.tutorial_hint = None
        with patch("gameplay_page.profile_manager.is_tutorial_pending", return_value=True), patch(
            "gameplay_page.TutorialHint"
        ), patch("app_settings.save_settings") as save:
            page._maybe_show_five_losses_tutorial()
            save.assert_not_called()
            page._sixth_level_losses_hint_pending = True
            page.tutorial_hint = object()
            page._maybe_show_five_losses_tutorial()
            save.assert_not_called()
            page.tutorial_hint = None
            page._maybe_show_five_losses_tutorial()
            save.assert_called_once_with({"always_lose_unlocked": True})

    def test_translations_fit_hint_and_dialog(self):
        pygame.font.init()
        self.addCleanup(set_language, get_language())
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            hint = TutorialHint((1680, 1050), None, MENU_FONT_PATH,
                                hint_id=SIXTH_LEVEL_LOSSES_HINT_ID, text=SIXTH_LEVEL_LOSSES_HINT_TEXT)
            self.assertLessEqual(len(hint.lines) * (hint.font.get_linesize() + 8),
                                 hint.checkbox_row.top - hint.panel.top - 65, language)
            font = pygame.font.Font(MENU_FONT_PATH, 30)
            for text in ALWAYS_LOSE_QUESTIONS:
                self.assertLessEqual(len(wrap_text(translate(text), font, 760)) * 42, 210)

    def test_streak_and_reset(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(profile_manager, "PROFILES_DIR", directory):
            self.assertEqual([record_level6_tutorial_result(1, False) for _ in range(6)],
                             [False, False, False, False, True, False])
            self.assertFalse(record_level6_tutorial_result(2, False))
            record_level6_tutorial_result(1, True)
            self.assertEqual(profile_manager.load_profile(1)["level6_loss_streak"], 0)

    def test_confirmation_chain_never_checks_box(self):
        page = SettingsPage.__new__(SettingsPage)
        page.values = {"always_lose_unlocked": True}
        page.original = dict(page.values)
        page.menu_sound = None
        with patch("settings_page.save_settings") as save:
            page._activate("always_lose")
            self.assertEqual(page.joke_dialog, 0)
            page._answer_joke(False)
            self.assertIsNone(page.joke_dialog)
            page._activate("always_lose")
            page._answer_joke(True)
            self.assertEqual(page.joke_dialog, 1)
            page._answer_joke(True)
            self.assertEqual(page.joke_dialog, 2)
            save.assert_called_once_with({"always_lose_warning_locked": True})
            page._answer_joke(True)
            page._activate("always_lose")
            self.assertEqual(page.joke_dialog, 2)
            self.assertNotIn("always_lose", page.values)

    def test_hidden_by_default_and_translated(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(load_settings(os.path.join(directory, "settings.json"))["always_lose_unlocked"])
        self.addCleanup(set_language, get_language())
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            for text in (SIXTH_LEVEL_LOSSES_HINT_TEXT, ALWAYS_LOSE_LABEL, *ALWAYS_LOSE_QUESTIONS):
                if language != "RU":
                    self.assertNotEqual(text, translate(text))
