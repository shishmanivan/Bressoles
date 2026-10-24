import unittest

import pygame

from gameplay_layout import compute_market_frames_layout
from gameplay_page import GameplayPage, SCREEN_WIDTH


class WaterlooForecastDragTests(unittest.TestCase):
    def setUp(self):
        self.page = GameplayPage.__new__(GameplayPage)
        self.page.frame = pygame.Surface((370, 540))
        self.page.waterloo_preview_movements = []

    def test_forecast_is_centered_over_three_market_fields(self):
        layout = compute_market_frames_layout(self.page.frame, SCREEN_WIDTH)
        left = layout["frame_rects"][0]["x"]
        right = layout["frame_rects"][-1]["x"] + layout["frame_width"]
        self.assertEqual(self.page._waterloo_forecast_rect().centerx, round((left + right) / 2))

    def test_drag_consumes_click_and_release_then_leaves_arrows_accessible(self):
        panel = self.page._waterloo_forecast_rect()
        start = (panel.x + 20, panel.y + 20)
        self.assertTrue(self.page._handle_waterloo_forecast_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start)))
        end = (start[0] + 100, start[1] + 200)
        self.assertTrue(self.page._handle_waterloo_forecast_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=end)))
        self.assertTrue(self.page._handle_waterloo_forecast_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=end)))
        self.assertEqual(self.page._waterloo_forecast_rect().topleft, (panel.x + 100, panel.y + 200))
        self.assertIsNone(self.page.waterloo_forecast_drag_offset)
        self.assertFalse(self.page._handle_waterloo_forecast_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start)))
