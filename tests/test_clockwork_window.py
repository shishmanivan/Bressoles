import os
import unittest
from unittest.mock import patch
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
from clockwork_window import ClockworkWindow, CAPTION, CLOSE
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate


class ClockworkTests(unittest.TestCase):
    def test_36_gears_tick_then_rest(self):
        pygame.font.init()
        window = ClockworkWindow(None, "egyptiennemncyr_condensedbold.ttf")
        screen = pygame.Surface((1680, 1050))
        with patch("clockwork_window.gear") as draw:
            window.draw(screen, 1200)
            first = draw.call_args_list[:]
            self.assertEqual(len(first), 36)
            draw.reset_mock()
            window.draw(screen, 1900)
            self.assertEqual(first, draw.call_args_list)
            draw.reset_mock()
            window.draw(screen, 2100)
            self.assertNotEqual(first, draw.call_args_list)

    def test_exit_and_localized_caption_fit(self):
        pygame.font.init()
        self.addCleanup(set_language, get_language())
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            window = ClockworkWindow(None, "egyptiennemncyr_condensedbold.ttf")
            self.assertLessEqual(len(window.lines), 2)
            if language != "RU":
                self.assertNotEqual(translate(CAPTION), CAPTION)
            self.assertTrue(window.accepts_close(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)))
            self.assertTrue(window.accepts_close(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=CLOSE.center)))
            self.assertFalse(window.accepts_close(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 400))))
