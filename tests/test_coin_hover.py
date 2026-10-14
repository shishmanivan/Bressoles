import unittest
from unittest.mock import Mock
import random

import pygame

from coin_hover import CoinHover
from start_page import StartPage


class CoinHoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = pygame.image.load('UI/Menu3_1.png')

    def test_individual_coin_grows_and_restores_original(self):
        effect = CoinHover(self.original)
        for ticks in (0, 50, 100, 150, 200):
            screen = self.original.copy()
            effect.draw(screen, screen.get_rect(), effect.coins[2][0].center, ticks)
        self.assertEqual(effect.amounts[2], 1)
        self.assertEqual(sum(a > 0 for a in effect.amounts), 1)
        self.assertNotEqual(pygame.image.tostring(screen, 'RGBA'),
                            pygame.image.tostring(self.original, 'RGBA'))
        for ticks in (250, 300, 350, 400):
            screen = self.original.copy()
            effect.draw(screen, screen.get_rect(), (0, 0), ticks)
        self.assertFalse(any(effect.amounts))
        self.assertEqual(pygame.image.tostring(screen, 'RGBA'),
                         pygame.image.tostring(self.original, 'RGBA'))

    def test_hit_regions_follow_coins_at_different_sizes(self):
        effect = CoinHover(self.original)
        for art in (pygame.Rect(0, 0, 800, 447), pygame.Rect(320, 80, 2560, 1430)):
            for index, (rect, _) in enumerate(effect.coins):
                center = (art.x + rect.centerx * art.width / 1678,
                          art.y + rect.centery * art.height / 937)
                self.assertEqual(effect.hit_test(center, art), index)
        self.assertIsNone(effect.hit_test((0, 0), art))

    def test_sound_only_on_entry_or_change_of_coin(self):
        effect = CoinHover(self.original)
        screen = self.original.copy()
        play = Mock()
        first, second = (effect.coins[index][0].center for index in (0, 2))
        for ticks, position in enumerate((first, first, second, second, (0, 0), second)):
            effect.draw(screen, screen.get_rect(), position, ticks * 16, play)
        self.assertEqual(play.call_count, 3)

    def test_random_coin_sounds_do_not_repeat_immediately(self):
        page = StartPage.__new__(StartPage)
        page.coin_sounds = [Mock() for _ in range(4)]
        page._coin_sound_random = random.Random(7)
        page._last_coin_sound = None
        for _ in range(40):
            previous = page._last_coin_sound
            page._play_coin_sound()
            self.assertIsNot(page._last_coin_sound, previous)
        self.assertTrue(all(sound.play.called for sound in page.coin_sounds))
        page.coin_sounds = []
        page._play_coin_sound()


if __name__ == '__main__':
    unittest.main()
