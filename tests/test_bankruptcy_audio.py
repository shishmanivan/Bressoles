import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import gameplay_bankruptcy_audio as audio


class BankruptcyAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.mixer.init()

    def tearDown(self):
        pygame.mixer.stop()

    def test_preload_is_silent_and_cached(self):
        page = SimpleNamespace()
        with mock.patch.object(audio, 'load_sound', wraps=audio.load_sound) as load:
            audio.preload(page)
            audio.preload(page)
        load.assert_called_once()
        self.assertFalse(pygame.mixer.get_busy())
        self.assertGreater(page._bankruptcy_crowd_source.get_length(), 2.4)

    def test_latest_random_start_has_full_clip_and_fades(self):
        page = SimpleNamespace()
        audio.preload(page)
        with mock.patch.object(audio._random, 'randint', side_effect=lambda first, last: last) as choose:
            audio.start(page, 2400)
        rate, bits, channels = pygame.mixer.get_init()
        width = abs(bits) // 8 * channels
        frames = round(rate * 2.4)
        total = len(page._bankruptcy_crowd_pcm) // width
        choose.assert_called_once_with(rate, total - frames)
        channel, clip, _ = page._bankruptcy_crowd_playback
        self.assertAlmostEqual(clip.get_length(), 2.4, places=3)
        self.assertEqual(clip.get_raw(), page._bankruptcy_crowd_pcm[-frames * width:])
        self.assertEqual(channel.get_volume(), 0)
        audio.update(page, 200)
        self.assertAlmostEqual(channel.get_volume(), .7, delta=.01)
        audio.update(page, 2200)
        self.assertAlmostEqual(channel.get_volume(), .35, delta=.01)
        audio.update(page, 2400)
        self.assertIsNone(page._bankruptcy_crowd_playback)
        self.assertFalse(channel.get_busy())

    def test_pause_and_stop_only_touch_owned_channel(self):
        channel, clip = mock.Mock(), mock.Mock()
        channel.get_sound.return_value = clip
        page = SimpleNamespace(_bankruptcy_crowd_playback=(channel, clip, 2400))
        audio.pause(page, True)
        audio.pause(page, False)
        channel.pause.assert_called_once()
        channel.unpause.assert_called_once()
        channel.get_sound.return_value = object()
        audio.stop(page)
        channel.stop.assert_not_called()
