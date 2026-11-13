import os
import tempfile
import unittest
from unittest.mock import patch, Mock
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import native_render as pygame
import profile_manager
from gameplay_tutorial import (record_level4_tutorial_result, FIVE_LOSSES_HINT_ID,
                               FIVE_LOSSES_HINT_TEXT, TutorialHint)
from gameplay_page import GameplayPage
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate


class FiveLossesTutorialTests(unittest.TestCase):
    def test_loss_tutorial_draws_above_report(self):
        page = GameplayPage.__new__(GameplayPage)
        page.win_lose_state = "lose"
        page.screen = Mock()
        order = Mock()
        page._draw_newspaper = order.report
        page._draw_newspaper_detail = order.detail
        page._draw_clockwork_overlay = order.background
        page.tutorial_hint = Mock()
        page.tutorial_hint.draw = order.hint
        for stage in ("newspaper", "finance_report"):
            order.reset_mock()
            page.result_report_stage = stage
            page._draw_gameplay_overlays()
            self.assertEqual(order.mock_calls[-1], unittest.mock.call.hint(page.screen))
            order.report.assert_called_once()

    def test_streak_persists_and_only_level_completion_resets_it(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(profile_manager, "PROFILES_DIR", directory):
            for _ in range(4):
                self.assertFalse(record_level4_tutorial_result(1, False))
                self.assertFalse(record_level4_tutorial_result(1, True))
            self.assertTrue(record_level4_tutorial_result(1, False))
            self.assertFalse(record_level4_tutorial_result(1, False))
            self.assertFalse(record_level4_tutorial_result(2, False))
            self.assertFalse(record_level4_tutorial_result(1, True, final_boss=True))
            self.assertEqual(profile_manager.load_profile(1)["level4_loss_streak"], 0)

    def test_pending_hint_shows_once_and_respects_checkbox(self):
        page = GameplayPage.__new__(GameplayPage)
        page.profile_slot, page.screen = 1, Mock()
        page.frame = page.font_path = page.ok1_button = None
        for pending in (True, False):
            page.tutorial_hint = None
            page._five_losses_hint_pending = True
            with patch("gameplay_page.profile_manager.is_tutorial_pending", return_value=pending), patch(
                "gameplay_page.TutorialHint"
            ) as hint:
                page._maybe_show_five_losses_tutorial()
                self.assertEqual(hint.called, pending)
                hint.reset_mock()
                page.tutorial_hint = None
                page._maybe_show_five_losses_tutorial()
                hint.assert_not_called()

    def test_translations_fit(self):
        pygame.font.init()
        self.addCleanup(set_language, get_language())
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            if language != "RU":
                self.assertNotEqual(translate(FIVE_LOSSES_HINT_TEXT), FIVE_LOSSES_HINT_TEXT)
            hint = TutorialHint((1680, 1050), None, "egyptiennemncyr_condensedbold.ttf",
                                hint_id=FIVE_LOSSES_HINT_ID, text=FIVE_LOSSES_HINT_TEXT)
            self.assertLessEqual(len(hint.lines) * (hint.font.get_linesize() + 8),
                                 hint.checkbox_row.top - hint.panel.top - 65, language)
