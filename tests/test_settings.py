import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from app_settings import load_music_volume, save_music_volume
from menu_music import BOSS_ROUND_MUSIC_PATHS, MenuMusic
from settings_page import SettingsPage
from start_page import StartPage


class MusicSettingsTests(unittest.TestCase):
    def test_round_end_leaves_music_playing_until_the_fade_finishes(self):
        track = BOSS_ROUND_MUSIC_PATHS[4]
        music = MenuMusic(fade_ms=0)
        music._boss_durations[track] = 570
        with (
            mock.patch("menu_music.pygame.mixer.get_init", return_value=True),
            mock.patch("menu_music.pygame.mixer.music") as player,
            mock.patch("menu_music.build_boss_music_loop", return_value=b""),
            mock.patch("menu_music.threading.Thread") as worker,
            mock.patch("menu_music.time.sleep"),
        ):
            music.play(track)
            music.return_to_menu()
            self.assertEqual(music.path, track)
            player.stop.assert_not_called()
            first_fade = worker.call_args.kwargs["target"]

            # If the next round opens early, its playback cancels the pending menu switch.
            player.get_busy.return_value = True
            music.play(track)
            first_fade()
            player.stop.assert_not_called()

            music.return_to_menu()
            player.get_pos.return_value = 182_400
            worker.call_args.kwargs["target"]()
            self.assertEqual(music.path, os.path.abspath(music.menu_path))
            player.stop.assert_called_once_with()
            music.play(track)
            player.play.assert_called_with(-1, start=182.4)

    def test_boss_music_resumes_across_rounds_without_counting_menu_time(self):
        appert = BOSS_ROUND_MUSIC_PATHS[4]
        smith = BOSS_ROUND_MUSIC_PATHS[2]
        music = MenuMusic(fade_ms=0)
        music._boss_durations.update({appert: 570, smith: 460})
        with (
            mock.patch("menu_music.pygame.mixer.get_init", return_value=True),
            mock.patch("menu_music.pygame.mixer.music") as player,
            mock.patch("menu_music.build_boss_music_loop", return_value=b""),
        ):
            music.play(appert)
            player.get_pos.return_value = 180_000
            music.play()
            player.get_pos.return_value = 40_000
            music.play(smith)
            player.play.assert_called_with(-1)
            player.get_pos.return_value = 25_000
            music.play(appert)
            player.play.assert_called_with(-1, start=180)
            player.get_pos.return_value = 405_000
            music.play()
            music.play(appert)
            player.play.assert_called_with(-1, start=15)
            music.play(smith)
            player.play.assert_called_with(-1, start=25)

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
