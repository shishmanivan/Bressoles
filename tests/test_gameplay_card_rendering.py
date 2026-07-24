import unittest

from gameplay_card_rendering import get_turns_text_position


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


if __name__ == "__main__":
    unittest.main()
