import unittest

import pygame

from gameplay_layout import compute_bottom_hand_layout, compute_lifecycle_card_x_positions


class LifecycleCardLayoutTests(unittest.TestCase):
    FRAME_X = 1247
    FRAME_WIDTH = 362
    PLACEHOLDER_WIDTH = 81
    CARD_WIDTH = 84

    def test_three_cards_match_the_top_panel_columns(self):
        positions = compute_lifecycle_card_x_positions(
            self.FRAME_X,
            self.FRAME_WIDTH,
            self.PLACEHOLDER_WIDTH,
            3,
        )
        spacing = (
            self.FRAME_WIDTH - 3 * self.PLACEHOLDER_WIDTH
        ) / 4

        self.assertEqual(
            positions,
            [
                self.FRAME_X + spacing,
                self.FRAME_X + spacing * 2 + self.PLACEHOLDER_WIDTH,
                self.FRAME_X + spacing * 3 + self.PLACEHOLDER_WIDTH * 2,
            ],
        )

    def test_outer_cards_stay_fixed_and_inside_frame(self):
        layouts = {
            count: compute_lifecycle_card_x_positions(
                self.FRAME_X,
                self.FRAME_WIDTH,
                self.PLACEHOLDER_WIDTH,
                count,
            )
            for count in (2, 4, 6, 7)
        }
        left_anchor, right_anchor = layouts[2]

        for count, positions in layouts.items():
            with self.subTest(count=count):
                self.assertEqual(positions[0], left_anchor)
                self.assertEqual(positions[-1], right_anchor)
                # Gameplay draws the card one pixel left of its placeholder;
                # the card itself is three pixels wider than the placeholder.
                self.assertGreater(positions[0] - 1, self.FRAME_X)
                self.assertLess(
                    positions[-1] - 1 + self.CARD_WIDTH,
                    self.FRAME_X + self.FRAME_WIDTH,
                )

    def test_seven_cards_overlap_between_the_fixed_edges(self):
        positions = compute_lifecycle_card_x_positions(
            self.FRAME_X,
            self.FRAME_WIDTH,
            self.PLACEHOLDER_WIDTH,
            7,
        )

        self.assertLess(positions[1] - positions[0], self.CARD_WIDTH)


class GrowingHandLayoutTests(unittest.TestCase):
    def test_large_hands_keep_the_seven_card_outer_anchors(self):
        frame = pygame.Surface((1154, 298))
        seven = compute_bottom_hand_layout(frame, 7, 1680, 1050)
        seven_rects = seven["slot_rects"]

        for hand_size in (8, 9, 10, 12):
            with self.subTest(hand_size=hand_size):
                layout = compute_bottom_hand_layout(frame, hand_size, 1680, 1050)
                rects = layout["slot_rects"]
                self.assertEqual(rects[0].x, seven_rects[0].x)
                self.assertEqual(rects[-1].x, seven_rects[-1].x)

    def test_large_hand_cards_stay_clear_of_frame_and_overlap(self):
        frame = pygame.Surface((1154, 298))
        layout = compute_bottom_hand_layout(frame, 10, 1680, 1050)
        rects = layout["slot_rects"]
        frame_left = layout["frame_x"]
        frame_right = frame_left + layout["frame_width"]

        self.assertGreaterEqual(rects[0].x - 2 - frame_left, 40)
        self.assertGreaterEqual(frame_right - (rects[-1].x - 2 + 142), 40)
        self.assertLess(rects[1].x - rects[0].x, 142)


if __name__ == "__main__":
    unittest.main()
