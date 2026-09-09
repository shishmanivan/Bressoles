import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from adaptive_ui import AnchoredElement, cover_geometry
from start_page import (
    StartPage,
    build_start_page_layout,
)


class AdaptiveStartPageTests(unittest.TestCase):
    def test_resize_replaces_old_scaled_sizes_and_reuses_current_ones(self):
        page = StartPage.__new__(StartPage)
        page._scaled_image_cache = {}
        sources = [pygame.Surface((30, 40), pygame.SRCALPHA) for _ in range(3)]
        for index, source in enumerate(sources):
            source.fill((30 + 40 * index, 70, 100, 140))
        retained = None
        for step in range(12):
            for source in sources:
                size = (50 + step * 2, 70 + step * 3)
                scaled = page._scaled(source, size)
                self.assertEqual(
                    pygame.image.tostring(scaled, "RGBA"),
                    pygame.image.tostring(pygame.transform.smoothscale(source, size), "RGBA"),
                )
                with mock.patch.object(pygame.transform, "smoothscale") as smoothscale:
                    self.assertIs(page._scaled(source, size), scaled)
                    smoothscale.assert_not_called()
                if retained is None:
                    retained = scaled
            self.assertEqual(len(page._scaled_image_cache), 3)
        # Eviction must not mutate an image still referenced elsewhere.
        self.assertEqual(retained.get_size(), (50, 70))
        self.assertEqual(retained.get_at((0, 0)), (30, 70, 100, 140))

    def test_resized_menu_matches_fresh_render_and_preserves_source_images(self):
        pygame.init()
        try:
            pygame.display.set_mode((320, 240))
            sources = [pygame.Surface(size, pygame.SRCALPHA) for size in ((344, 144), (217, 72), (83, 79), (217, 72), (93, 79), (216, 25), (124, 43))]
            for index, image in enumerate(sources):
                image.fill((40 + 35 * index, 90, 130, 255))
                pygame.draw.rect(image, (240, 210, 90, 255), (5, 5, 20, 20))
            original_pixels = [pygame.image.tostring(image, "RGBA") for image in sources]
            with (
                mock.patch.object(StartPage, "_load_image", side_effect=sources),
                mock.patch("start_page.load_button_sound"),
            ):
                page = StartPage(pygame.Surface((1680, 1050)), None, None, profile_name="Benchmark")
            for size in ((1680, 1050), (1280, 720), (1920, 1080), (1680, 1050)):
                page.screen = pygame.Surface(size)
                page.draw()
                pixels = pygame.image.tostring(page.screen, "RGB")
                self.assertEqual(len(page._scaled_image_cache), 7)
                # A fresh scaling pass is the reference for both old and new caches.
                page._scaled_image_cache.clear()
                page.draw()
                self.assertEqual(pygame.image.tostring(page.screen, "RGB"), pixels)
            self.assertEqual([pygame.image.tostring(image, "RGBA") for image in sources], original_pixels)
        finally:
            pygame.quit()

    def test_menu_activation_uses_button_sound(self):
        page = StartPage.__new__(StartPage)
        page.button_sound = mock.Mock()

        self.assertEqual(page._activate_menu_item(1), "options")

        page.button_sound.play.assert_called_once_with()

    def test_cover_crops_sides_on_16_by_9(self):
        scaled_size, position = cover_geometry((3440, 1440), (1920, 1080))
        self.assertEqual(scaled_size, (2580, 1080))
        self.assertEqual(position, (-330, 0))

    def test_cover_reveals_full_master_background_at_its_native_ratio(self):
        scaled_size, position = cover_geometry((3440, 1440), (3440, 1440))
        self.assertEqual(scaled_size, (3440, 1440))
        self.assertEqual(position, (0, 0))

    def test_layout_uses_viewport_anchors_and_frame_relative_rows(self):
        layout = build_start_page_layout((1920, 1080), (2172, 724), (834, 794), (2172, 724))
        self.assertEqual(layout.title_rect.left, 77)
        self.assertEqual(layout.title_rect.top, 54)
        self.assertEqual(layout.menu_rect.right, 1920 - 77)
        self.assertEqual(layout.menu_rect.centery, 540)
        self.assertEqual(layout.menu_rect.height, 505)
        self.assertAlmostEqual(layout.menu_rect.width / layout.menu_rect.height, 834 / 794, places=2)
        self.assertEqual(layout.ribbon_rect.width, 1152)
        self.assertAlmostEqual(layout.ribbon_rect.width / layout.ribbon_rect.height, 2172 / 724, places=2)
        self.assertEqual(layout.ribbon_rect.centerx, 826)
        self.assertGreater(layout.ribbon_rect.bottom, 1080)
        self.assertEqual(layout.main_back_rect.height, 1026)
        self.assertEqual(layout.main_back_rect.left, 0)
        self.assertEqual(layout.main_back_rect.top, 22)
        self.assertTrue(layout.main_back_rect.colliderect(layout.ribbon_rect))
        self.assertLess(layout.main_back_rect.right, layout.menu_rect.left)
        self.assertEqual(layout.bottom_rect, pygame.Rect(0, 855, 1920, 225))
        self.assertEqual(layout.top_rect.centerx, layout.menu_rect.centerx)
        self.assertEqual(layout.top_rect.width, round(layout.menu_rect.width * 1.42 * 0.85))
        self.assertGreater(layout.top_rect.bottom, layout.menu_rect.top)
        self.assertTrue(all(layout.menu_rect.collidepoint(point) for point in layout.row_centers))
        self.assertEqual(len(layout.row_centers), 5)

    def test_ultrawide_does_not_push_edge_anchored_ui_beyond_max_margin(self):
        layout = build_start_page_layout((3440, 1440), (2172, 724), (834, 794), (2172, 724))
        self.assertEqual(layout.title_rect.left, 90)
        self.assertEqual(layout.menu_rect.right, 3440 - 90)
        self.assertEqual(layout.title_rect.width, 760)
        self.assertEqual(layout.menu_rect.height, 544)
        self.assertEqual(layout.ribbon_rect.width, 1300)
        self.assertEqual(layout.ribbon_rect.centerx, 1540)
        self.assertEqual(layout.main_back_rect.height, 1200)
        self.assertEqual(layout.main_back_rect.left, 0)
        self.assertLess(layout.main_back_rect.right, layout.menu_rect.left)
        self.assertEqual(layout.bottom_rect.width, 2159)
        self.assertEqual(layout.bottom_rect.bottom, 1440)
        self.assertEqual(layout.top_rect.centerx, layout.menu_rect.centerx)

    def test_ribbon_scales_down_for_small_viewports_without_losing_its_ratio(self):
        layout = build_start_page_layout((800, 600), (2172, 724), (834, 794), (2172, 724))
        self.assertEqual(layout.ribbon_rect.width, 520)
        self.assertAlmostEqual(layout.ribbon_rect.width / layout.ribbon_rect.height, 3.0, places=1)
        self.assertEqual(layout.ribbon_rect.centerx, 344)
        self.assertLess(layout.ribbon_rect.top, 600)
        self.assertGreater(layout.ribbon_rect.bottom, 600)
        self.assertGreaterEqual(
            layout.main_back_rect.bottom,
            layout.ribbon_rect.top + round(layout.ribbon_rect.height * 0.55),
        )

    def test_left_illustration_stays_clear_of_menu_and_behind_ribbon(self):
        for viewport in (
            (800, 600),
            (1280, 720),
            (1366, 768),
            (1680, 1050),
            (1920, 1080),
            (2560, 1080),
            (3440, 1440),
        ):
            with self.subTest(viewport=viewport):
                layout = build_start_page_layout(
                    viewport,
                    (2172, 724),
                    (834, 794),
                    (2172, 724),
                    (1021, 843),
                )
                self.assertLess(layout.main_back_rect.right, layout.menu_rect.left)
                self.assertGreaterEqual(
                    layout.main_back_rect.bottom,
                    layout.ribbon_rect.top + round(layout.ribbon_rect.height * 0.55),
                )

    def test_generic_anchor_supports_all_viewport_edges_and_center(self):
        self.assertEqual(
            AnchoredElement("right", "bottom", 20, 30).rect((100, 50), (800, 600)),
            pygame.Rect(680, 520, 100, 50),
        )

if __name__ == "__main__":
    unittest.main()
