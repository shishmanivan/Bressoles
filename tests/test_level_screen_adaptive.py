import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from asset_loaders import find_font_path_or_exit
from game_screen import GameScreen, PAGE_ARROW_FRAME_MS
from level_screen_helpers import LEVEL_CONTENT_SIZE, level_content_rect


class AdaptiveLevelScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.font_path = find_font_path_or_exit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make_page(self, size=(1680, 1050), **kwargs):
        return GameScreen(pygame.Surface(size), None, self.font_path, **kwargs)

    def viewport_point(self, page, point):
        rect = level_content_rect(page.screen.get_size())
        return (
            round(rect.x + point[0] * rect.width / LEVEL_CONTENT_SIZE[0]),
            round(rect.y + point[1] * rect.height / LEVEL_CONTENT_SIZE[1]),
        )

    def click(self, page, position):
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position)
        with mock.patch("pygame.event.get", return_value=[event]):
            return page.handle_input()

    def test_grid_keeps_its_proportions_and_reference_size(self):
        self.assertEqual(level_content_rect(LEVEL_CONTENT_SIZE), pygame.Rect(0, 0, 1680, 1050))
        for size in ((1280, 720), (1920, 1080), (2560, 1080), (3440, 1440), (800, 600)):
            with self.subTest(size=size):
                rect = level_content_rect(size)
                self.assertTrue(pygame.Rect((0, 0), size).contains(rect))
                self.assertAlmostEqual(rect.width / rect.height, 1680 / 1050, places=2)
        self.assertEqual(level_content_rect((1920, 1080)).size,
                         level_content_rect((2560, 1080)).size)

    def test_background_is_cover_and_changes_after_viewport_resize(self):
        page = self.make_page((1920, 1080))
        self.assertEqual(page.background.get_size(), (3440, 1440))
        page._draw_cards = mock.Mock()
        page.draw()
        self.assertEqual(page._viewport_background.get_size(), (2580, 1080))
        self.assertEqual(page._background_position, (-330, 0))
        # The transparent UI layer must not leave a dark border over the master.
        self.assertEqual(page.screen.get_at((0, 500)),
                         page._viewport_background.get_at((330, 500)))
        page.screen = pygame.Surface((3440, 1440))
        page.draw()
        self.assertEqual(page._viewport_background.get_size(), (3440, 1440))
        self.assertEqual(page._background_position, (0, 0))

    def test_level_clicks_follow_scaled_centered_cards(self):
        page = self.make_page()
        page.button_sound = None
        original_positions = list(page.normal_card_positions)
        for size in ((1280, 720), (1920, 1080), (3440, 1440)):
            with self.subTest(size=size):
                page.screen = pygame.Surface(size)
                self.assertEqual(self.click(page, self.viewport_point(page, page.arrow_rect.center)), "level_1")
                self.assertEqual(page.normal_card_positions, original_positions)
                self.assertIsNone(self.click(page, (0, 0)))

    def test_navigation_and_level_eight_use_same_transform(self):
        page = self.make_page((1280, 720), progress_flags={"level_8_unlocked": True})
        page.button_sound = None
        self.assertIsNone(self.click(page, self.viewport_point(page, page.next_page_rect.center)))
        self.assertEqual(page.level_page_index, 0)
        started = page._page_animation_started_at
        page._update_page_animation(started + 3 * PAGE_ARROW_FRAME_MS)
        self.assertEqual(page.level_page_index, 1)
        page._update_page_animation(started + 4 * PAGE_ARROW_FRAME_MS)
        self.assertEqual(self.click(page, self.viewport_point(page, page.normal_arrow_rects[1].center)), "level_8")
        self.assertIsNone(self.click(page, self.viewport_point(page, page.previous_page_rect.center)))
        self.assertEqual(page.level_page_index, 1)
        page._update_page_animation(page._page_animation_started_at + 3 * PAGE_ARROW_FRAME_MS)
        self.assertEqual(page.level_page_index, 0)

    def test_page_changes_only_on_fourth_frame_and_ignores_repeated_clicks(self):
        page = self.make_page(progress_flags={"level_8_unlocked": True})
        page.page_arrow_sound = mock.Mock()
        self.click(page, page.next_page_rect.center)
        page.page_arrow_sound.play.assert_called_once_with()
        started = page._page_animation_started_at
        for frame in range(3):
            page._update_page_animation(started + frame * PAGE_ARROW_FRAME_MS)
            self.assertEqual(page._page_animation_frame, frame)
            self.assertEqual(page.level_page_index, 0)
            self.click(page, page.next_page_rect.center)
            self.assertEqual(page._page_animation_started_at, started)
            self.assertIsNone(self.click(page, page.arrow_rect.center))
        page._update_page_animation(started + 3 * PAGE_ARROW_FRAME_MS - 1)
        self.assertEqual(page.level_page_index, 0)
        page._update_page_animation(started + 3 * PAGE_ARROW_FRAME_MS)
        self.assertEqual(page._page_animation_frame, 3)
        self.assertEqual(page.level_page_index, 1)
        self.assertEqual(page._page_animation_source, 0)
        page._update_page_animation(started + 4 * PAGE_ARROW_FRAME_MS)
        self.assertIsNone(page._page_animation_started_at)
        self.assertEqual(page._page_animation_frame, 0)
        self.assertEqual(page.level_page_index, 1)

        page.page_arrow_sound.play.assert_called_once_with()
        self.click(page, page.previous_page_rect.center)
        self.assertEqual(page.page_arrow_sound.play.call_count, 2)

    def test_slow_frame_still_shows_fourth_frame_and_arrows_are_mirrored(self):
        page = self.make_page(progress_flags={"level_8_unlocked": True})
        for right, left in zip(page.page_arrow_frames, page.page_arrow_back_frames):
            self.assertEqual(right.get_size(), (150, 100))
            self.assertEqual(pygame.image.tobytes(left, "RGBA"),
                             pygame.image.tobytes(pygame.transform.flip(right, True, False), "RGBA"))
        page._start_page_animation(1)
        late = page._page_animation_started_at + 1000
        page._update_page_animation(late)
        self.assertEqual(page.level_page_index, 1)
        self.assertEqual(page._page_animation_frame, 3)
        self.assertIsNotNone(page._page_animation_started_at)
        page._update_page_animation(late + PAGE_ARROW_FRAME_MS)
        self.assertIsNone(page._page_animation_started_at)

    def test_test_mode_scroll_and_clicks_remain_in_content_coordinates(self):
        page = self.make_page((1280, 720), test_mode=True)
        page.button_sound = None
        page.scroll_y = page.test_card_positions[6][1] - 75
        arrow = page.test_card_rects[6].move(0, -page.scroll_y)
        self.assertEqual(self.click(page, self.viewport_point(page, arrow.center)), "level_7")
        target = page.screen
        page.draw()
        self.assertIs(page.screen, target)


if __name__ == "__main__":
    unittest.main()
