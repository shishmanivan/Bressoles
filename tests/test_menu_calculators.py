import unittest

import pygame

from start_page import CALCULATOR_CHANGE_INTERVAL, MENU_FONT_PATH, StartPage


class MenuCalculatorTests(unittest.TestCase):
    def test_drums_hold_roll_and_finish_without_a_boundary_jump(self):
        pygame.font.init()
        try:
            page = StartPage.__new__(StartPage)
            page.font_path = MENU_FONT_PATH
            page._font_cache = {}
            page._calculator_assets = None
            def pixels(seconds, offset=0):
                return pygame.image.tostring(page._render_calculator_panel(seconds, offset), 'RGB')
            for offset in (0, 10000):
                initial = pixels(0, offset)
                self.assertEqual(initial, pixels(1, offset))
                self.assertNotEqual(initial, pixels(2.8, offset))
                self.assertNotEqual(initial, pixels(CALCULATOR_CHANGE_INTERVAL, offset))
                self.assertEqual(pixels(CALCULATOR_CHANGE_INTERVAL - 0.0001, offset),
                                 pixels(CALCULATOR_CHANGE_INTERVAL, offset))
            self.assertNotEqual(pixels(0), pixels(0, 10000))
        finally:
            pygame.font.quit()


if __name__ == '__main__':
    unittest.main()
