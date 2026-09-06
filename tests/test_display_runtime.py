import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from display_runtime import (
    ADAPTIVE_DISPLAY_FLAGS,
    FALLBACK_DISPLAY_FLAGS,
    LOGICAL_SCREEN_SIZE,
    create_game_display,
)


class DisplayRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_adaptive_display_uses_a_resizable_native_viewport(self):
        screen = create_game_display()

        self.assertEqual(screen.get_size(), LOGICAL_SCREEN_SIZE)
        self.assertTrue(ADAPTIVE_DISPLAY_FLAGS & pygame.RESIZABLE)
        self.assertFalse(ADAPTIVE_DISPLAY_FLAGS & pygame.SCALED)

    def test_display_falls_back_to_the_fixed_mode_when_scaling_fails(self):
        fallback_surface = pygame.Surface(LOGICAL_SCREEN_SIZE)
        with mock.patch.object(
            pygame.display,
            "set_mode",
            side_effect=[pygame.error("renderer unavailable"), fallback_surface],
        ) as set_mode:
            screen = create_game_display()

        self.assertIs(screen, fallback_surface)
        self.assertEqual(set_mode.call_args_list[0].args, (LOGICAL_SCREEN_SIZE, ADAPTIVE_DISPLAY_FLAGS))
        self.assertEqual(set_mode.call_args_list[1].args, (LOGICAL_SCREEN_SIZE, FALLBACK_DISPLAY_FLAGS))


if __name__ == "__main__":
    unittest.main()
