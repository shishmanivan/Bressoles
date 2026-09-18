import os
from pathlib import Path
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from gameplay_assets import _load_arrow_sequence


ARROWS = Path(__file__).resolve().parents[1] / "GameplayPage" / "Arrows"


class GameplayArrowAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((60, 60))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def load_frames(self, kind, direction):
        return [
            pygame.image.load(str(ARROWS / f"{kind}-{direction}-{index}.png"))
            for index in range(3)
        ]

    def pixels(self, image, rect=None):
        if rect is not None:
            image = image.subsurface(rect)
        return pygame.image.tostring(image, "RGBA")

    def test_head_moves_but_shaft_and_stop_bar_stay_pixel_identical(self):
        plain = self.load_frames("single", "up")
        barred = self.load_frames("all", "up")
        tips = [frame.get_bounding_rect(min_alpha=128).top for frame in plain]
        self.assertLess(tips[0], tips[1])
        self.assertLess(tips[1], tips[2])
        for index in range(3):
            with self.subTest(frame=index):
                self.assertEqual(
                    self.pixels(plain[0], (0, 300, 512, 212)),
                    self.pixels(plain[index], (0, 300, 512, 212)),
                )
                self.assertEqual(
                    self.pixels(barred[0], (0, 0, 512, 17)),
                    self.pixels(barred[index], (0, 0, 512, 17)),
                )
                self.assertEqual(
                    self.pixels(plain[index], (0, 20, 512, 492)),
                    self.pixels(barred[index], (0, 20, 512, 492)),
                )

    def test_down_arrows_are_exact_rotations_with_transparent_backgrounds(self):
        for kind in ("single", "all"):
            up = self.load_frames(kind, "up")
            down = self.load_frames(kind, "down")
            for index in range(3):
                with self.subTest(kind=kind, frame=index):
                    self.assertEqual(
                        self.pixels(down[index]),
                        self.pixels(pygame.transform.rotate(up[index], 180)),
                    )
                    for frame in (up[index], down[index]):
                        self.assertEqual(frame.get_size(), (512, 512))
                        for point in ((0, 0), (511, 0), (0, 511), (511, 511), (20, 256)):
                            self.assertEqual(frame.get_at(point).a, 0)

    def test_all_sequences_load_three_distinct_frames_at_game_button_size(self):
        for kind in ("single", "all"):
            for direction in ("up", "down"):
                paths = [str(ARROWS / f"{kind}-{direction}-{index}.png") for index in range(3)]
                frames, primary = _load_arrow_sequence(paths[0], paths[1:], "Missing arrow:")
                self.assertIs(primary, frames[0])
                self.assertEqual([frame.get_size() for frame in frames], [(60, 60)] * 3)
                self.assertEqual(len({self.pixels(frame) for frame in frames}), 3)


if __name__ == "__main__":
    unittest.main()
