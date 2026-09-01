import unittest

from gameplay_card_rendering import (
    get_bear_modifier_font_size,
    get_bear_modifier_x,
    get_bear_modifier_y,
    get_turns_text_position,
)


class CardTurnsPositionTests(unittest.TestCase):
    def test_multiplier_card_number_keeps_same_gap_after_baked_label(self):
        card_width = 140
        card_height = 242
        regular_x, regular_y = get_turns_text_position(11, card_width, card_height)
        multiplier_x, multiplier_y = get_turns_text_position(17, card_width, card_height)

        # Measured right edges of "Turns:" in the 640 px source artwork.
        regular_label_right = 361 / 640 * card_width
        multiplier_label_right = 311 / 640 * card_width

        self.assertAlmostEqual(
            regular_x - regular_label_right,
            multiplier_x - multiplier_label_right,
            delta=0.1,
        )
        self.assertAlmostEqual(
            multiplier_y - regular_y,
            1.5 * card_height / 244,
        )
        self.assertEqual(
            get_turns_text_position(18, card_width, card_height),
            (multiplier_x, multiplier_y),
        )

    def test_regulation_variant_uses_card_11_counter_math(self):
        card_width = 140
        card_height = 242
        self.assertEqual(
            get_turns_text_position(20, card_width, card_height),
            get_turns_text_position(11, card_width, card_height),
        )
        self.assertEqual(
            get_turns_text_position(21, card_width, card_height),
            get_turns_text_position(11, card_width, card_height),
        )


class BearModifierPositionTests(unittest.TestCase):
    def test_storage_uses_shop_horizontal_proportion(self):
        self.assertAlmostEqual(get_bear_modifier_x(0, 142) / 142, 0.53)
        self.assertAlmostEqual(get_bear_modifier_x(0, 102) / 102, 0.53)

    def test_two_digit_discount_is_smaller_and_shifted_left(self):
        self.assertEqual(get_bear_modifier_font_size(102), 20)
        self.assertEqual(
            get_bear_modifier_font_size(102, multidigit=True),
            18,
        )
        self.assertAlmostEqual(
            get_bear_modifier_x(0, 102) - get_bear_modifier_x(0, 102, multidigit=True),
            102 * 0.025,
        )

    def test_shop_position_remains_pixel_identical(self):
        self.assertAlmostEqual(
            get_bear_modifier_y(0, 244, 34, adjust_mode="shop"),
            244 * 0.07 - 4,
        )

    def test_storage_percentage_uses_title_centerline_with_visual_nudge(self):
        shop_y = get_bear_modifier_y(0, 244, 34, adjust_mode="shop")
        storage_y = get_bear_modifier_y(0, 176, 27)

        self.assertAlmostEqual(
            (shop_y + 34 / 2) / 244,
            (storage_y + 27 / 2 + 0.75) / 176,
        )


if __name__ == "__main__":
    unittest.main()
