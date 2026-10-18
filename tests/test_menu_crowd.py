import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from menu_crowd import MenuCrowdAnimation, ping_pong_frame, CROWD_CACHE_FRAMES
from start_page import StartPage, MENU_CROWD_VOLUME


class CrowdAmbienceTests(unittest.TestCase):
    def test_ambience_loops_and_stops_on_every_menu_exit(self):
        for result in ('quit', 'start', 'profile', 'options', 'languages'):
            with self.subTest(result=result):
                page = StartPage.__new__(StartPage)
                page.handle_input = mock.Mock(return_value=result)
                sound, channel = mock.Mock(), mock.Mock()
                sound.play.return_value = channel
                channel.get_sound.return_value = sound
                with mock.patch('start_page.load_sound', return_value=sound):
                    self.assertEqual(page.run(), result)
                sound.play.assert_called_once_with(loops=-1, fade_ms=300)
                channel.set_volume.assert_called_once_with(MENU_CROWD_VOLUME)
                channel.stop.assert_called_once_with()

    def test_missing_audio_does_not_block_menu(self):
        page = StartPage.__new__(StartPage)
        page.handle_input = mock.Mock(return_value='start')
        with mock.patch('start_page.load_sound', return_value=None):
            self.assertEqual(page.run(), 'start')


class CrowdTimingTests(unittest.TestCase):
    def test_starts_at_one_then_reverses_at_twelve_without_repeating_endpoints(self):
        self.assertEqual([ping_pong_frame(i / 24, 24, 289) for i in range(5)],
                         [24, 25, 26, 27, 28])
        self.assertEqual([ping_pong_frame(i / 24, 24, 289) for i in range(262, 267)],
                         [286, 287, 288, 287, 286])
        self.assertEqual([ping_pong_frame(i / 24, 24, 289) for i in range(526, 531)],
                         [26, 25, 24, 25, 26])

    def test_longer_video_still_stays_between_one_and_twelve(self):
        self.assertEqual(ping_pong_frame(0, 24, 481), 24)
        self.assertEqual(ping_pong_frame(11, 24, 481), 288)
        self.assertEqual(ping_pong_frame(22, 24, 481), 24)
        self.assertEqual(ping_pong_frame(10, 24, 1), 0)


class CrowdRenderingTests(unittest.TestCase):
    def test_mask_resize_and_bounded_cache(self):
        pygame.init()
        try:
            pygame.display.set_mode((1, 1))
            original = pygame.image.load('UI/Menu3_1.png').convert_alpha()
            effect = MenuCrowdAnimation(original)
            self.assertIsNotNone(effect.sequence)
            for width in (800, 1678, 2560):
                art = pygame.Rect(10, 20, width, round(width * 937 / 1678))
                screen = pygame.Surface((art.right + 10, art.bottom + 10))
                screen.fill((15, 25, 35))
                effect.draw(screen, art, 0)
                # Unrelated artwork/menu remains untouched, including the
                # transparent upper-right corner within the animation patch.
                self.assertEqual(screen.get_at((art.right - 1, art.bottom - 1))[:3], (15, 25, 35))
                px = art.x + round(680 * width / 1678)
                py = art.y + round(230 * art.height / 937)
                self.assertEqual(screen.get_at((px, py))[:3], (15, 25, 35))
            for tick in range(0, 1000, 42):
                effect.draw(screen, art, tick)
            self.assertLessEqual(len(effect.frames), CROWD_CACHE_FRAMES)
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
