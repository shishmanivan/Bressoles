import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from app_settings import load_music_volume, save_music_volume
from menu_music import MenuMusic
from settings_page import SettingsPage
from start_page import StartPage


class MusicSettingsTests(unittest.TestCase):
    def test_music_volume_round_trip_and_clamping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "settings.json")
            self.assertEqual(load_music_volume(path), 1.0)
            self.assertEqual(save_music_volume(0.35, path), 0.35)
            self.assertEqual(load_music_volume(path), 0.35)
            save_music_volume(4, path)
            self.assertEqual(load_music_volume(path), 1.0)

    def test_menu_music_volume_is_applied_immediately_when_active(self):
        music = MenuMusic(fade_ms=0, volume=0.75)
        music._loaded = True
        music._menu_active = True

        with mock.patch("menu_music.pygame.mixer.music.set_volume") as set_volume:
            self.assertEqual(music.set_volume(0.4), 0.4)

        self.assertEqual(music.volume, 0.4)
        self.assertEqual(music._volume, 0.4)
        set_volume.assert_called_once_with(0.4)

    def test_slider_updates_volume_and_callback(self):
        changed = []
        page = SettingsPage.__new__(SettingsPage)
        page.slider_rect = pygame.Rect(100, 200, 400, 12)
        page.music_volume = 0.0
        page.on_volume_change = changed.append

        page._set_volume_from_x(300)

        self.assertEqual(page.music_volume, 0.5)
        self.assertEqual(changed, [0.5])

    def test_start_page_returns_options_result(self):
        page = StartPage.__new__(StartPage)
        page.handle_input = mock.Mock(return_value="options")
        page.draw = mock.Mock()
        page.clock = mock.Mock()

        self.assertEqual(page.run(), "options")
        page.draw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
