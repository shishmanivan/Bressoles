import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from adaptive_ui import AnchoredElement, cover_geometry
from start_page import (
    MENU_FONT_PATH,
    PAPER_COLOR,
    StartPage,
    build_start_page_layout,
)


class AdaptiveStartPageTests(unittest.TestCase):
    def test_press_feedback_defers_action_and_plays_sound_once(self):
        pygame.init()
        try:
            page = StartPage.__new__(StartPage)
            page._pending_action = None
            page._pressed_target = None
            page.button_sound = mock.Mock()
            with mock.patch("pygame.time.get_ticks", return_value=100):
                page._begin_press(0, "start")
                page._begin_press(1, "options")
            self.assertEqual(page._pressed_target, 0)
            page.button_sound.play.assert_called_once_with()
            with mock.patch("pygame.event.get", return_value=[]):
                with mock.patch("pygame.time.get_ticks", return_value=150):
                    self.assertIsNone(page.handle_input())
                with mock.patch("pygame.time.get_ticks", return_value=190):
                    self.assertEqual(page.handle_input(), "start")
                self.assertIsNone(page.handle_input())
            self.assertIsNone(page._pressed_target)
        finally:
            pygame.quit()

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
            sources = [
                pygame.Surface(size, pygame.SRCALPHA)
                for size in ((344, 144), (217, 72), (168, 94))
            ]
            for index, image in enumerate(sources):
                image.fill((40 + 35 * index, 90, 130, 255))
                pygame.draw.rect(image, (240, 210, 90, 255), (5, 5, 20, 20))
            original_pixels = [pygame.image.tostring(image, "RGBA") for image in sources]
            with (
                mock.patch.object(StartPage, "_load_image", side_effect=sources),
                mock.patch("start_page.load_sound"),
            ):
                page = StartPage(pygame.Surface((1680, 1050)), None, None, profile_name="Benchmark")
            self.assertEqual(page.font_path, MENU_FONT_PATH)
            self.assertFalse(page._get_font(40).get_bold())
            self.assertEqual(PAPER_COLOR, (77, 63, 50))
            for size in ((1680, 1050), (1280, 720), (1920, 1080), (1680, 1050)):
                page.screen = pygame.Surface(size)
                page.draw()
                pixels = pygame.image.tostring(page.screen, "RGB")
                self.assertEqual(len(page._scaled_image_cache), 3)
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
        layout = build_start_page_layout((1920, 1080), (2172, 724), (1678, 937))
        self.assertEqual(layout.title_rect.left, 77)
        self.assertEqual(layout.title_rect.top, 76)
        self.assertEqual(layout.menu_image_rect.width, 1920)
        self.assertEqual(layout.menu_image_rect.center, (960, 540))
        self.assertAlmostEqual(
            layout.menu_image_rect.width / layout.menu_image_rect.height,
            1678 / 937,
            places=2,
        )
        self.assertTrue(layout.menu_image_rect.contains(layout.menu_rect))
        self.assertTrue(all(layout.menu_rect.collidepoint(point) for point in layout.row_centers))
        self.assertEqual(len(layout.row_centers), 5)

    def test_ultrawide_reveals_master_background_beside_menu3(self):
        layout = build_start_page_layout((3440, 1440), (2172, 724), (1678, 937))
        self.assertEqual(layout.title_rect.left, 90)
        self.assertEqual(layout.title_rect.width, 760)
        self.assertEqual(layout.menu_image_rect.height, 1440)
        self.assertEqual(layout.menu_image_rect.centery, 720)
        self.assertGreater(layout.menu_image_rect.left, 0)
        self.assertLess(layout.menu_image_rect.right, 3440)

    def test_menu3_and_embedded_frame_stay_proportional_at_common_sizes(self):
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
                    viewport, (2172, 724), (1678, 937)
                )
                self.assertTrue(pygame.Rect((0, 0), viewport).contains(layout.menu_image_rect))
                self.assertAlmostEqual(
                    layout.menu_image_rect.width / layout.menu_image_rect.height,
                    1678 / 937,
                    places=2,
                )
                self.assertTrue(layout.menu_image_rect.contains(layout.menu_rect))
                self.assertTrue(all(layout.menu_rect.collidepoint(point) for point in layout.row_centers))

    def test_generic_anchor_supports_all_viewport_edges_and_center(self):
        self.assertEqual(
            AnchoredElement("right", "bottom", 20, 30).rect((100, 50), (800, 600)),
            pygame.Rect(680, 520, 100, 50),
        )

if __name__ == "__main__":
    unittest.main()
