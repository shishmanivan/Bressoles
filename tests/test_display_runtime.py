import os
import gc
from pathlib import Path
import subprocess
import sys
import unittest
import weakref
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import display_runtime

from display_runtime import (
    ADAPTIVE_DISPLAY_FLAGS,
    FALLBACK_DISPLAY_FLAGS,
    LOGICAL_SCREEN_SIZE,
    create_game_display,
    apply_display_settings,
    fit_window_size,
)


class DisplayRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        retained_window = mock.patch.object(display_runtime, '_display_window', None)
        retained_window.start()
        self.addCleanup(retained_window.stop)

    def test_borrowed_window_survives_after_caller_releases_it(self):
        class BorrowedWindow:
            pass

        with mock.patch('pygame._sdl2.video.Window') as window_class:
            window_class.from_display_module.side_effect = BorrowedWindow
            window = display_runtime._borrow_display_window()
            reference = weakref.ref(window)
            del window
            gc.collect()
            self.assertIsNotNone(reference())
            self.assertIs(reference(), display_runtime._display_window)

    def test_new_display_replaces_retained_wrapper(self):
        with mock.patch('pygame._sdl2.video.Window') as window_class:
            window_class.from_display_module.side_effect = [mock.Mock(), mock.Mock()]
            previous = display_runtime._borrow_display_window()
            current = display_runtime._borrow_display_window()
            self.assertIsNot(previous, current)
            self.assertIs(display_runtime._display_window, current)

    def test_native_events_keep_a_live_window_after_display_creation(self):
        # Isolate a native access violation so a regression cannot kill the
        # whole test runner. SDL's dummy driver still converts native events.
        source = '''
import gc
import pygame
import display_runtime

pygame.init()
display_runtime._windows_geometry = lambda: ((0, 0, 1920, 1080), None, None)
try:
    for _ in range(5):
        screen = display_runtime.create_game_display()
        gc.collect()
        allocated = [pygame.Rect(0, 0, 10, 10) for _ in range(1000)]
        pygame.display.set_mode((screen.get_width() + 1, screen.get_height() + 1))
        events = [event for event in pygame.event.get() if hasattr(event, 'window')]
        assert events, 'Expected native window events'
        assert all(event.window is display_runtime._display_window for event in events)
finally:
    pygame.quit()
'''
        result = subprocess.run(
            [sys.executable, '-X', 'faulthandler', '-c', source],
            cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy'),
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_fullscreen_then_window_uses_native_window_flags(self):
        with mock.patch.object(pygame.display, 'set_mode') as set_mode:
            apply_display_settings({'resolution': (1680,1050), 'fullscreen': True})
            apply_display_settings({'resolution': (1440,900), 'fullscreen': False})
        first, second = set_mode.call_args_list
        self.assertTrue(first.args[1] & pygame.FULLSCREEN)
        self.assertEqual(second.args[0], (1440,900))
        self.assertTrue(second.args[1] & pygame.RESIZABLE)
        self.assertFalse(second.args[1] & (pygame.FULLSCREEN | pygame.NOFRAME))

    def test_fullscreen_retains_wrapper_for_the_new_native_window(self):
        surface = pygame.Surface((1680, 1050))
        with (
            mock.patch.object(display_runtime.sys, 'platform', 'win32'),
            mock.patch.object(pygame.display, 'get_driver', return_value='windows'),
            mock.patch.object(pygame.display, 'set_mode', return_value=surface),
            mock.patch('pygame._sdl2.video.Window') as window_class,
        ):
            self.assertIs(
                apply_display_settings({'resolution': (1680, 1050), 'fullscreen': True}),
                surface,
            )
            window_class.from_display_module.assert_called_once()
            self.assertIs(display_runtime._display_window, window_class.from_display_module.return_value)

    def test_large_window_leaves_room_for_title_bar_and_taskbar(self):
        width, height = fit_window_size((1680,1050), (0,0,1680,1010))
        self.assertLessEqual(width, 1512)
        self.assertLessEqual(height + 48, 909)
        self.assertAlmostEqual(width / height, 1680 / 1050, places=2)

    def test_small_requested_window_is_clamped_to_minimum(self):
        self.assertEqual(fit_window_size((800,600), (-1920,0,1920,1040)), (1280,800))

    def test_window_is_restored_decorated_and_centered_on_its_monitor(self):
        work = (-1920,0,1920,1040)
        window = mock.Mock()
        with mock.patch('display_runtime._windows_geometry', return_value=(work,(1696,927),None)), mock.patch(
                'pygame._sdl2.video.Window') as window_class:
            window_class.from_display_module.return_value = window
            screen = create_game_display()
        window.restore.assert_called_once()
        self.assertFalse(window.borderless)
        self.assertTrue(window.resizable)
        self.assertEqual(window.position, (-1808,56))
        self.assertEqual(screen.get_size(), fit_window_size(LOGICAL_SCREEN_SIZE,work))
        self.assertIs(display_runtime._display_window, window)

    def test_minimum_width_and_height_are_independent(self):
        self.assertEqual(fit_window_size((400,900), None), (1280,900))
        self.assertEqual(fit_window_size((1400,200), None), (1400,800))
        self.assertEqual(fit_window_size((200,200), None), (1280,800))

    def test_fitting_to_small_desktop_never_shrinks_below_supported_size(self):
        self.assertEqual(fit_window_size((1680,1050),(0,0,1280,720)), (1280,800))

    def test_minimum_is_installed_when_returning_from_fullscreen(self):
        with mock.patch('display_runtime._set_minimum_window_size') as minimum:
            apply_display_settings({'resolution':(1680,1050),'fullscreen':True})
            minimum.assert_not_called()
            apply_display_settings({'resolution':(1680,1050),'fullscreen':False})
            minimum.assert_called_once()


if __name__ == "__main__":
    unittest.main()
