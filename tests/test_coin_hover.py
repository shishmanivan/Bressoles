import unittest

import pygame

from coin_hover import CoinHover


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


if __name__ == '__main__':
    unittest.main()
