import os
import unittest
from unittest.mock import patch, Mock
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
from clockwork_window import ClockworkWindow, CAPTION, CLOSE
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate
from gameplay_page import GameplayPage
from clockwork_window import BUTTON


class ClockworkTests(unittest.TestCase):
    def test_report_blocks_all_background_input(self):
        for outcome in ('win', 'lose'):
            for stage in ('newspaper', 'finance_report', 'card_report', 'market_report'):
                page = GameplayPage.__new__(GameplayPage)
                page.tutorial_hint = None
                page.win_lose_state = outcome
                page.result_report_stage = stage
                page.screen = Mock()
                page.mouse_pos = Mock(return_value=(0, 0))
                page._handle_newspaper_input = Mock(return_value=None)
                page._open_pause_menu = Mock()
                page._start_card_drag = Mock()
                page._handle_deck_view_event = Mock()
                page._handle_pause_menu_event = Mock()
                page._clockwork_window = Mock()
                # Even stale overlay flags cannot intercept report events.
                page.pause_menu_active = page.deck_view_active = True
                events = [
                    pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=BUTTON.center),
                    pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(1500, 950)),
                    pygame.event.Event(pygame.MOUSEMOTION, pos=(100, 700)),
                    pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(100, 700)),
                    pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
                    pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                ]
                page.events = Mock(return_value=events)
                page.handle_input()
                self.assertEqual(page._handle_newspaper_input.call_count, len(events))
                page._open_pause_menu.assert_not_called()
                page._start_card_drag.assert_not_called()
                page._handle_deck_view_event.assert_not_called()
                page._handle_pause_menu_event.assert_not_called()
                page._clockwork_window.accepts_close.assert_not_called()
                with patch('clockwork_window.draw_button') as button:
                    page._draw_clockwork_overlay()
                    button.assert_called_once_with(page.screen)
                    page._clockwork_window.draw.assert_not_called()

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
