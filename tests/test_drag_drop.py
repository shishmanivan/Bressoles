import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from gameplay_page import GameplayPage


class PlaceholderDropZoneTests(unittest.TestCase):
    def setUp(self):
        self.page = GameplayPage.__new__(GameplayPage)

    def test_drop_zone_accepts_cursor_ten_pixels_outside_placeholder(self):
        placeholder = {"slot": 0, "rect": pygame.Rect(20, 20, 100, 100)}

        candidates = self.page._placeholder_hit_candidates([placeholder], (10, 60))

        self.assertEqual(candidates, [placeholder])
        self.assertEqual(
            self.page._placeholder_hit_candidates([placeholder], (9, 60)),
            [],
        )

    def test_exact_neighbor_does_not_hide_expanded_valid_placeholder(self):
        first = {"slot": 0, "rect": pygame.Rect(0, 0, 100, 100)}
        neighbor = {"slot": 1, "rect": pygame.Rect(105, 0, 100, 100)}

        candidates = self.page._placeholder_hit_candidates([first, neighbor], (105, 50))

        self.assertEqual(candidates[0], neighbor)
        self.assertIn(first, candidates)


if __name__ == "__main__":
    unittest.main()
