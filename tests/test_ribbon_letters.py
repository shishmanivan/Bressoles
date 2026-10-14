import unittest
from unittest import mock

import pygame

from ribbon_letters import RibbonLetterHover


class RibbonLetterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = pygame.image.load('UI/Menu3_1.png')

    def test_hover_sound_plays_once_per_letter_and_original_returns(self):
        effect = RibbonLetterHover(self.image)
        screen = self.image.copy()
        artwork = screen.get_rect()
        sound = mock.Mock()
        first = effect.letters[7][0].center
        second = effect.letters[8][0].center
        for ticks in (0, 50, 100, 150):
            screen = self.image.copy()
            effect.draw(screen, artwork, first, ticks, sound)
        sound.assert_called_once_with()
        self.assertEqual(effect.amounts[7], 1)
        self.assertNotEqual(pygame.image.tostring(screen, 'RGBA'),
                            pygame.image.tostring(self.image, 'RGBA'))
        effect.draw(screen, artwork, second, 200, sound)
        self.assertEqual(sound.call_count, 2)
        for ticks in (250, 300, 350, 400):
            screen = self.image.copy()
            effect.draw(screen, artwork, (0, 0), ticks, sound)
        self.assertEqual(sound.call_count, 2)
        self.assertFalse(any(effect.amounts))
        self.assertEqual(pygame.image.tostring(screen, 'RGBA'),
                         pygame.image.tostring(self.image, 'RGBA'))

    def test_letter_hit_areas_follow_scaled_and_centered_artwork(self):
        effect = RibbonLetterHover(self.image)
        for artwork in (pygame.Rect(0, 0, 800, 447), pygame.Rect(300, 20, 2560, 1430)):
            for index, (bounds, _, _) in enumerate(effect.letters):
                point = (artwork.left + bounds.centerx * artwork.width / 1678,
                         artwork.top + bounds.centery * artwork.height / 937)
                self.assertEqual(effect.hit_test(point, artwork), index)
        self.assertIsNone(effect.hit_test((0, 0), artwork))

    def test_exclamation_mask_contains_entire_stroke_and_dot(self):
        effect = RibbonLetterHover(self.image)
        bounds, glyph, patch = effect.letters[-1]
        dark_pixels = 0
        for y in range(779, 820):
            for x in range(1087, 1102):
                if sum(self.image.get_at((x, y))[:3]) / 3 >= 125:
                    continue
                dark_pixels += 1
                self.assertTrue(bounds.collidepoint(x, y))
                local = (x - bounds.x, y - bounds.y)
                self.assertEqual(patch.get_at(local).a, 255)
                self.assertGreater(glyph.get_at(local).a, 30)
        self.assertGreater(dark_pixels, 180)


if __name__ == '__main__':
    unittest.main()
