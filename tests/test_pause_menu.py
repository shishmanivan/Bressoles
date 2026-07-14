import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from gameplay_page import GameplayPage
from gameplay_pause import build_pause_menu_layout, get_pause_menu_action


class PauseMenuLayoutTests(unittest.TestCase):
    def test_main_menu_buttons_fit_panel_without_overlap(self):
        layout = build_pause_menu_layout((1680, 1050))
        panel = layout["panel"]
        buttons = list(layout["buttons"].values())

        self.assertEqual(list(layout["buttons"]), ["continue", "save_exit", "restart"])
        self.assertTrue(all(panel.contains(rect) for rect in buttons))
        self.assertTrue(all(not first.colliderect(second) for first, second in zip(buttons, buttons[1:])))
        for action, rect in layout["buttons"].items():
            self.assertEqual(get_pause_menu_action(layout, rect.center), action)

    def test_confirmation_replaces_main_actions(self):
        layout = build_pause_menu_layout((1680, 1050), confirmation=True)
        self.assertEqual(list(layout["buttons"]), ["cancel", "restart_confirm"])


class PauseMenuActionTests(unittest.TestCase):
    def setUp(self):
        self.page = GameplayPage.__new__(GameplayPage)
        self.page.pause_menu_active = True
        self.page.pause_menu_requested = False
        self.page.pause_restart_confirmation = False
        self.page._save_active_game = mock.Mock()
        self.page._record_stats_result = mock.Mock()

    def test_save_and_exit_persists_current_state(self):
        result = self.page._handle_pause_menu_action("save_exit")

        self.assertEqual(result, "main_menu")
        self.page._save_active_game.assert_called_once_with()
        self.assertFalse(self.page.pause_menu_active)

    def test_restart_requires_confirmation_and_records_a_loss(self):
        self.assertIsNone(self.page._handle_pause_menu_action("restart"))
        self.assertTrue(self.page.pause_restart_confirmation)

        result = self.page._handle_pause_menu_action("restart_confirm")

        self.assertEqual(result, "restart_level")
        self.page._record_stats_result.assert_called_once_with(False)
        self.assertFalse(self.page.pause_menu_active)


if __name__ == "__main__":
    unittest.main()
