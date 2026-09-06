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
        layout = build_start_page_layout((1920, 1080), (2172, 724), (834, 794))
        self.assertEqual(layout.title_rect.left, 77)
        self.assertEqual(layout.title_rect.top, 54)
        self.assertEqual(layout.menu_rect.right, 1920 - 77)
        self.assertEqual(layout.menu_rect.centery, 540)
        self.assertEqual(layout.menu_rect.height, 505)
        self.assertAlmostEqual(layout.menu_rect.width / layout.menu_rect.height, 834 / 794, places=2)
        self.assertTrue(all(layout.menu_rect.collidepoint(point) for point in layout.row_centers))
        self.assertEqual(len(layout.row_centers), 5)

    def test_ultrawide_does_not_push_edge_anchored_ui_beyond_max_margin(self):
        layout = build_start_page_layout((3440, 1440), (2172, 724), (834, 794))
        self.assertEqual(layout.title_rect.left, 90)
        self.assertEqual(layout.menu_rect.right, 3440 - 90)
        self.assertEqual(layout.title_rect.width, 760)
        self.assertEqual(layout.menu_rect.height, 544)

    def test_generic_anchor_supports_all_viewport_edges_and_center(self):
        self.assertEqual(
            AnchoredElement("right", "bottom", 20, 30).rect((100, 50), (800, 600)),
            pygame.Rect(680, 520, 100, 50),
        )

if __name__ == "__main__":
    unittest.main()
