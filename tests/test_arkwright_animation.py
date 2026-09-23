import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from gameplay_page import GameplayPage


class ArkwrightAnimationTests(unittest.TestCase):
    def make_page(self, quantities=(40, 30, 30)):
        page = GameplayPage.__new__(GameplayPage)
        page.boss_steals_shares = True
        page.win_lose_state = None
        page.turn_resolution_active = True
        page.Aquantity, page.Bquantity, page.Cquantity = quantities
        page.Money = 17
        page._record_arkwright_stat = mock.Mock()
        page._finish_turn_after_arkwright_share_theft = mock.Mock()
        return page

    def test_each_theft_amount_drains_to_exact_targets_with_three_pulses(self):
        for roll, stolen in ((0, 90), (0.03, 50), (0.1, 30)):
            with self.subTest(stolen=stolen):
                page = self.make_page()
                with (
                    mock.patch("gameplay_page.random.random", return_value=roll),
                    mock.patch("gameplay_page.random.randint", return_value=1),
                    mock.patch("gameplay_page.pygame.time.get_ticks", return_value=0),
                ):
                    self.assertTrue(page._apply_boss_share_theft_if_needed())
                self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), (40, 30, 30))
                anim = page.arkwright_share_theft_animation
                self.assertEqual(sum(anim["target_quantities"].values()), 100 - stolen)
                previous = dict(anim["start_quantities"])
                for tick, scale in ((0, 1), (250, 1.25), (500, 1), (750, 1.25), (1000, 1), (1250, 1.25)):
                    with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=tick):
                        page.update_arkwright_share_theft_animation()
                        self.assertAlmostEqual(page._get_boss_effect_pulse_scale(), scale)
                    for key, target in anim["target_quantities"].items():
                        value = getattr(page, key)
                        self.assertGreaterEqual(value, target)
                        self.assertLessEqual(value, previous[key])
                        previous[key] = value
                    page._finish_turn_after_arkwright_share_theft.assert_not_called()
                with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=1500):
                    page.update_arkwright_share_theft_animation()
                    page.update_arkwright_share_theft_animation()
                for key, target in anim["target_quantities"].items():
                    self.assertEqual(getattr(page, key), target)
                self.assertEqual(page.Money, 17)
                self.assertEqual(page._get_boss_effect_pulse_scale(), 1)
                page._finish_turn_after_arkwright_share_theft.assert_called_once_with()
                page._record_arkwright_stat.assert_called_once()

    def test_turn_and_result_wait_without_rolling_theft_again(self):
        page = self.make_page()
        with (
            mock.patch("gameplay_page.random.random", return_value=0.1) as roll,
            mock.patch("gameplay_page.pygame.time.get_ticks", return_value=0),
        ):
            page._finalize_turn_resolution()
            page._finalize_turn_resolution()
            page._check_win_lose()
            self.assertFalse(page._apply_boss_share_theft_if_needed())
        roll.assert_called_once_with()
        page._finish_turn_after_arkwright_share_theft.assert_not_called()
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=1500):
            page.update_arkwright_share_theft_animation()
        page._finish_turn_after_arkwright_share_theft.assert_called_once_with()

    def test_no_theft_has_no_animation_or_delay(self):
        for quantities, roll in (((4, 3, 3), 0), ((40, 30, 30), 0.5), ((0, 0, 0), 0)):
            with self.subTest(quantities=quantities, roll=roll):
                page = self.make_page(quantities)
                with mock.patch("gameplay_page.random.random", return_value=roll):
                    page._finalize_turn_resolution()
                self.assertFalse(page._is_boss_penalty_animating())
                self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), quantities)
                page._finish_turn_after_arkwright_share_theft.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
