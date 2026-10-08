import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from native_render import draw as native_draw
from adaptive_page import AdaptivePage, adaptive_draw, content_rect, draw_modal_shade


class ModalCompositionTests(unittest.TestCase):
    def test_shade_covers_viewport_and_dims_composed_alpha_artwork(self):
        pygame.init()
        self.addCleanup(pygame.quit)
        pygame.display.set_mode((1, 1))

        class Page(AdaptivePage):
            shaded = False

            @adaptive_draw
            def draw(self):
                # Transparent, translucent and opaque artwork must all be
                # darkened after blending with the same paper background.
                for x, alpha in ((100, 0), (400, 100), (700, 255)):
                    tile = pygame.Surface((160, 160), pygame.SRCALPHA)
                    tile.fill((220, 200, 180, alpha))
                    self.screen.blit(tile, (x, 100))
                if self.shaded:
                    draw_modal_shade(self.screen, (0, 0, 0, 110))
                    native_draw.rect(self.screen, (236, 226, 201), (900, 400, 200, 200))

        with mock.patch('adaptive_page.load_scaled_image', return_value=None):
            page = Page()
            page.init_viewport(pygame.Surface((1920, 1080)))
        for size in ((1920, 1080), (1366, 768), (1280, 800), (3440, 1440)):
            with self.subTest(size=size):
                page.viewport = pygame.Surface(size)
                page.shaded = False
                page.draw()
                expected = page.viewport.copy()
                shade = pygame.Surface(size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 110))
                expected.blit(shade, (0, 0))
                page.shaded = True
                page.draw()
                rect = content_rect(size)
                points = [(0, 0), (size[0]-1, size[1]-1)]
                points += [(rect.x + round(x * rect.width / 1680),
                            rect.y + round(150 * rect.height / 1050))
                           for x in (150, 450, 750)]
                for point in points:
                    self.assertEqual(page.viewport.get_at(point), expected.get_at(point))
                panel_point = (rect.x + round(1000 * rect.width / 1680),
                               rect.y + round(500 * rect.height / 1050))
                self.assertTrue(all(abs(actual - wanted) <= 5 for actual, wanted in zip(page.viewport.get_at(panel_point)[:3], (236, 226, 201))))
                page.shaded = False
                page.draw()
                self.assertEqual(page.viewport.get_at((0, 0))[:3], (235, 220, 190))


if __name__ == '__main__':
    unittest.main()
