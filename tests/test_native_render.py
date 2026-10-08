import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import native_render as native
from adaptive_page import AdaptivePage, adaptive_draw, content_rect, draw_modal_shade


class NativeRenderTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def tearDown(self):
        pygame.quit()

    def pixels(self, image):
        return pygame.image.tostring(image, 'RGBA')

    def test_images_use_original_after_multiple_intermediate_sizes(self):
        original = pygame.Surface((121, 121), pygame.SRCALPHA)
        for x in range(121):
            pygame.draw.line(original, (x * 2, (x % 3) * 120, 70, 255), (x, 0), (120-x, 120))
        image = native.transform.smoothscale(native.Surface.wrap(original), (60, 60))
        image = native.transform.smoothscale(image, (40, 40))
        canvas = native.Canvas((100, 100))
        canvas.configure((73, 73))
        canvas.blit(image, (10, 10))
        expected = pygame.Surface((73, 73), pygame.SRCALPHA)
        expected.blit(pygame.transform.smoothscale(original, (29, 29)), (7, 7))
        self.assertEqual(self.pixels(canvas.pixels), self.pixels(expected))

    def test_font_pixels_match_fresh_native_font_including_composite_widget(self):
        for scale in (.73, 1.03, 1.37):
            with self.subTest(scale=scale):
                canvas = native.Canvas((300, 100))
                canvas.configure((round(300 * scale), round(100 * scale)))
                widget = native.Surface((300, 100), pygame.SRCALPHA)
                widget.blit(native.font.Font(None, 32).render('Native 123', True, 'white'), (0, 0))
                canvas.blit(widget, (0, 0))
                expected = pygame.Surface(canvas.pixels.get_size(), pygame.SRCALPHA)
                expected.blit(pygame.font.Font(None, round(32 * scale)).render('Native 123', True, 'white'), (0, 0))
                self.assertEqual(self.pixels(canvas.pixels), self.pixels(expected))

    def test_adjacent_tiles_have_no_gaps_at_fractional_scale(self):
        widget = native.Surface((100, 20), pygame.SRCALPHA)
        tile = native.Surface((10, 20), pygame.SRCALPHA)
        tile.fill('white')
        for x in range(0, 100, 10):
            widget.blit(tile, (x, 0))
        canvas = native.Canvas((100, 20))
        for size in ((73, 15), (103, 21), (137, 27)):
            canvas.configure(size)
            canvas.fill((0, 0, 0, 0))
            canvas.blit(widget, (0, 0))
            self.assertTrue(all(canvas.pixels.get_at((x, size[1]//2)) == (255,255,255,255)
                                for x in range(size[0])))

    def test_clip_and_resize_use_native_pixels(self):
        canvas = native.Canvas((100, 100))
        for size in ((73, 73), (137, 137)):
            canvas.configure(size)
            canvas.fill((0, 0, 0, 0))
            canvas.set_clip((20, 20, 30, 30))
            native.draw.rect(canvas, 'red', (0, 0, 100, 100))
            self.assertEqual(canvas.get_at((25,25)), pygame.Color('red'))
            self.assertEqual(canvas.get_at((10,10)).a, 0)
            self.assertEqual(canvas.get_at((60,60)).a, 0)

    def test_present_never_resizes_completed_frame_or_modal_layers(self):
        class Page(AdaptivePage):
            @adaptive_draw
            def draw(self):
                native.draw.rect(self.screen, 'red', (0, 0, 1680, 1050))
                draw_modal_shade(self.screen, (0,0,0,110))
                native.draw.rect(self.screen, 'white', (500,300,600,400))
        with mock.patch('adaptive_page.load_scaled_image', return_value=None):
            page = Page()
            page.init_viewport(pygame.Surface((1366, 768)))
        with mock.patch('pygame.transform.smoothscale', side_effect=AssertionError('frame resampled')):
            page.draw()
        self.assertEqual(page.screen.pixels.get_size(), content_rect((1366,768)).size)
        self.assertEqual(page.screen.modal_layers[0][0].get_size(), page.screen.pixels.get_size())


if __name__ == '__main__':
    unittest.main()
