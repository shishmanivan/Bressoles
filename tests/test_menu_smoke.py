import math
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from start_page import (
    SMOKE_REGION, SMOKE_REFERENCE_SIZE, SMOKE_SOURCES, SmokeSource, StartPage,
    _make_smoke_sprites, _smoke_particles, build_start_page_layout,
)


class MenuSmokeTests(unittest.TestCase):
    def test_puff_is_born_rises_expands_and_dissolves(self):
        source = SmokeSource((162, 660), spawn_interval=10, lifetime=5)
        born = list(_smoke_particles(source, 0))[0]
        middle = list(_smoke_particles(source, 2))[0]
        dying = list(_smoke_particles(source, 4.99))[0]
        self.assertEqual(born[3], 0)
        self.assertGreater(middle[3], 0.1)
        self.assertLess(middle[1], born[1])
        self.assertGreater(middle[0], born[0])
        self.assertGreater(dying[2], middle[2])
        self.assertLess(dying[3], 0.001)
        self.assertEqual(list(_smoke_particles(source, 5)), [])

    def test_long_running_emitter_has_bounded_particle_count(self):
        for source in SMOKE_SOURCES:
            for seconds in (0, 20, 3600, 86400):
                particles = list(_smoke_particles(source, seconds))
                self.assertLessEqual(len(particles), math.ceil(source.lifetime / source.spawn_interval))
                self.assertTrue(all(0 <= particle[3] <= 1 for particle in particles))

    def test_animation_stays_local_at_common_window_sizes(self):
        page = StartPage.__new__(StartPage)
        page.menu_image = pygame.Surface(SMOKE_REFERENCE_SIZE)
        page._smoke_started_at = 0
        page._smoke_sprites = _make_smoke_sprites()
        for size in ((800, 600), (1920, 1080), (3440, 1440)):
            page.screen = pygame.Surface(size, pygame.SRCALPHA)
            layout = build_start_page_layout(size, (2172, 724), SMOKE_REFERENCE_SIZE)
            art = layout.menu_image_rect
            sx, sy = art.width / 1678, art.height / 937
            x, y, width, height = SMOKE_REGION
            region = pygame.Rect(art.left + round(x * sx), art.top + round(y * sy),
                                 round(width * sx), round(height * sy))
            frames = []
            for ticks in (0, 2000):
                page.screen.fill((0, 0, 0, 0))
                clip = page.screen.get_clip()
                with mock.patch("pygame.time.get_ticks", return_value=ticks):
                    page._draw_smoke(layout)
                bounds = page.screen.get_bounding_rect()
                self.assertGreater(bounds.width, 0)
                self.assertTrue(region.contains(bounds))
                self.assertFalse(bounds.colliderect(layout.menu_rect))
                self.assertEqual(page.screen.get_clip(), clip)
                frames.append(pygame.image.tostring(page.screen.subsurface(region), "RGBA"))
            self.assertNotEqual(*frames)
        page.screen.fill((0, 0, 0, 0))
        with mock.patch("start_page.SMOKE_SOURCES", ()):
            page._draw_smoke(layout)
        self.assertEqual(page.screen.get_bounding_rect().width, 0)


if __name__ == "__main__":
    unittest.main()
