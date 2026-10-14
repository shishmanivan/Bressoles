import os
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from menu_chart import CHART_RECT, MenuChartReveal, chart_reveal_x


class MenuChartTests(unittest.TestCase):
    def test_reveal_advances_once_and_restores_exact_original(self):
        pygame.init()
        try:
            pygame.display.set_mode((1, 1))
            original = pygame.image.load('UI/Menu3_1.png').convert()
            for size in ((800, 447), (1678, 937), (2560, 1430)):
                effect = MenuChartReveal(original)
                base = pygame.transform.smoothscale(original, size)
                artwork = base.get_rect()
                early = base.copy()
                effect.draw(early, artwork, 100)
                self.assertNotEqual(pygame.image.tostring(early, 'RGB'), pygame.image.tostring(base, 'RGB'))
                middle = base.copy()
                effect.draw(middle, artwork, 3500)
                self.assertNotEqual(pygame.image.tostring(early, 'RGB'), pygame.image.tostring(middle, 'RGB'))
                for ticks in (10000, 60000):
                    complete = base.copy()
                    effect.draw(complete, artwork, ticks)
                    self.assertEqual(pygame.image.tostring(complete, 'RGB'), pygame.image.tostring(base, 'RGB'))
            self.assertEqual(chart_reveal_x(0), chart_reveal_x(0.7))
            self.assertEqual(chart_reveal_x(60), CHART_RECT.right)
            stops = [chart_reveal_x(i / 20) for i in range(180)]
            self.assertEqual(stops, sorted(stops))
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
