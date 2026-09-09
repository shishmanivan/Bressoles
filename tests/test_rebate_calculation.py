import unittest

from gameplay_trade_actions import calculate_rebate_sale_percent


class RebateCalculationTests(unittest.TestCase):
    def test_base_card_combinations_and_gold_copies(self):
        for full_price, discounted, gold_count, expected in (
            (False, False, 0, None), (False, True, 0, 90),
            (True, False, 0, 100), (True, True, 0, 120),
            (False, False, 1, 130), (False, True, 1, 140),
            (True, False, 1, 140), (True, True, 1, 150),
            (False, False, 2, 160), (False, True, 2, 170),
            (True, False, 2, 170), (True, True, 2, 180),
        ):
            with self.subTest(full_price=full_price, discounted=discounted, gold_count=gold_count):
                self.assertEqual(calculate_rebate_sale_percent(
                    full_price=full_price, discounted=discounted, gold_rebate_count=gold_count,
                ), expected)

    def test_gold_bonuses_apply_once_and_only_with_gold_rebate(self):
        for gold_count, expected in ((0, 140), (1, 199), (2, 229)):
            with self.subTest(gold_count=gold_count):
                self.assertEqual(calculate_rebate_sale_percent(
                    full_price=True, discounted=True, gold_rebate_count=gold_count,
                    amplifier_bonus=25, fall_bonus=4, additional_bonus_percent=20,
                ), expected)

    def test_additional_bonuses_require_base_rebate_and_have_no_hundred_percent_cap(self):
        self.assertIsNone(calculate_rebate_sale_percent(
            full_price=False, discounted=False, gold_rebate_count=0,
            amplifier_bonus=25, fall_bonus=4, additional_bonus_percent=500,
        ))
        self.assertEqual(calculate_rebate_sale_percent(
            full_price=False, discounted=True, gold_rebate_count=0,
            additional_bonus_percent=500,
        ), 590)


if __name__ == "__main__":
    unittest.main()
