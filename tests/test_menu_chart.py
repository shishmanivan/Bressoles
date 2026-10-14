import os
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from menu_chart import (CHART_RECT, MenuChartReveal, chart_reveal_x, chart_phase,
                        CHART_START_DELAY, CHART_DRAW_SECONDS, CHART_HOLD_SECONDS)


class MenuChartTests(unittest.TestCase):
    def test_reveal_cycles_and_preserves_first_original(self):
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
                cycle = CHART_DRAW_SECONDS + CHART_HOLD_SECONDS
                for seconds in (CHART_START_DELAY + CHART_DRAW_SECONDS + 0.5,
                                CHART_START_DELAY + cycle * 3 + CHART_DRAW_SECONDS + 0.5):
                    complete = base.copy()
                    effect.draw(complete, artwork, 100 + round(seconds * 1000))
                    expected = base.copy()
                    sx, sy = size[0] / 1678, size[1] / 937
                    target = pygame.Rect(round(CHART_RECT.x * sx), round(CHART_RECT.y * sy),
                                         round(CHART_RECT.width * sx), round(CHART_RECT.height * sy))
                    expected.blit(pygame.transform.smoothscale(original.subsurface(CHART_RECT), target.size), target)
                    self.assertEqual(pygame.image.tostring(complete, 'RGB'), pygame.image.tostring(expected, 'RGB'))
                for index in (1, 2):
                    complete = base.copy()
                    seconds = CHART_START_DELAY + cycle * index + CHART_DRAW_SECONDS + 0.5
                    effect.draw(complete, artwork, 100 + round(seconds * 1000))
                    self.assertNotEqual(pygame.image.tostring(complete, 'RGB'), pygame.image.tostring(base, 'RGB'))
                    held = base.copy()
                    effect.draw(held, artwork, 100 + round((seconds + 1) * 1000))
                    self.assertEqual(pygame.image.tostring(held, 'RGB'), pygame.image.tostring(complete, 'RGB'))
            self.assertEqual(chart_reveal_x(0), chart_reveal_x(0.7))
            self.assertEqual(chart_reveal_x(60), CHART_RECT.right)
            stops = [chart_reveal_x(i / 20) for i in range(180)]
            self.assertEqual(stops, sorted(stops))
        finally:
            pygame.quit()

    def test_phase_holds_then_advances_and_loops(self):
        duration = CHART_DRAW_SECONDS + CHART_HOLD_SECONDS
        for index in range(7):
            start = CHART_START_DELAY + duration * index
            self.assertEqual(chart_phase(start + 0.001)[0], index % 3)
            self.assertEqual(chart_phase(start + duration - 0.001)[0], index % 3)

    def test_falling_chart_stays_behind_newspaper(self):
        pygame.init()
        try:
            pygame.display.set_mode((1, 1))
            effect = MenuChartReveal(pygame.image.load('UI/Menu3_1.png'))
            for x in range(174, 185):
                for y in range(85, 121):
                    self.assertEqual(effect.charts[1].get_at((x, y)), effect.clean.get_at((x, y)))
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
