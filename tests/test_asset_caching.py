import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import asset_loaders
import boss_page
import round_page_assets
from gameplay_page import GameplayPage
from shop_page import ShopPage


class AssetCachingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1680, 1050))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        asset_loaders._scaled_image_cache.clear()
        boss_page._boss_animation_frames_cache.clear()
        round_page_assets._boss_visual_assets_cache.clear()

    def test_round_boss_assets_are_loaded_once_and_geometry_stays_local(self):
        first_anchor = pygame.Rect(300, 700, 100, 100)
        second_anchor = pygame.Rect(600, 500, 100, 100)

        with mock.patch.object(pygame.image, "load", wraps=pygame.image.load) as image_load:
            first_icon, first_rect, first_frames = round_page_assets.load_boss_icon_assets(
                1, 0, "1_Watt.png", 4, 4, first_anchor, first_anchor
            )
            first_load_count = image_load.call_count
            second_icon, second_rect, second_frames = round_page_assets.load_boss_icon_assets(
                1, 0, "1_Watt.png", 4, 4, second_anchor, second_anchor
            )

        self.assertGreater(first_load_count, 0)
        self.assertEqual(image_load.call_count, first_load_count)
        self.assertIs(second_icon, first_icon)
        self.assertIsNot(second_frames, first_frames)
        self.assertTrue(all(left is right for left, right in zip(first_frames, second_frames)))
        self.assertNotEqual(first_rect.topleft, second_rect.topleft)

        pixels_before = pygame.image.tostring(first_icon, "RGBA")
        self.screen.blit(first_icon, first_rect)
        self.assertEqual(pygame.image.tostring(first_icon, "RGBA"), pixels_before)

    def test_boss_page_animation_frames_are_shared_between_instances(self):
        with mock.patch.object(pygame.image, "load", wraps=pygame.image.load) as image_load:
            first_frames = boss_page._load_boss_animation_frames("1_Watt.png")
            first_load_count = image_load.call_count
            second_frames = boss_page._load_boss_animation_frames("1_Watt.png")

        self.assertEqual(len(first_frames), 7)
        self.assertEqual(image_load.call_count, first_load_count)
        self.assertIsNot(first_frames, second_frames)
        self.assertTrue(all(left is right for left, right in zip(first_frames, second_frames)))

    def test_gameplay_boss_icons_use_the_shared_scaled_image_cache(self):
        first_page = GameplayPage.__new__(GameplayPage)
        first_page.current_boss_icon_cache = {}
        second_page = GameplayPage.__new__(GameplayPage)
        second_page.current_boss_icon_cache = {}

        with mock.patch.object(pygame.image, "load", wraps=pygame.image.load) as image_load:
            first_icon = first_page._load_current_boss_icon("1_Watt.png")
            first_load_count = image_load.call_count
            second_icon = second_page._load_current_boss_icon("1_Watt.png")

        self.assertIsNotNone(first_icon)
        self.assertEqual(image_load.call_count, first_load_count)
        self.assertIs(second_icon, first_icon)

    def test_shop_coin_rendering_caches_scale_and_text_surfaces(self):
        page = ShopPage.__new__(ShopPage)
        page.screen = pygame.Surface((300, 200), pygame.SRCALPHA)
        page.coin_image = pygame.Surface((54, 54), pygame.SRCALPHA)
        page._coin_image_cache = {(54, 54): page.coin_image}
        page._coin_text_cache = {}
        page.balance_font = pygame.font.Font(None, 48)
        small_font = pygame.font.Font(None, 30)

        with mock.patch.object(pygame.transform, "smoothscale", wraps=pygame.transform.smoothscale) as smoothscale:
            page._draw_coin_amount(5, (150, 100), small_font)
            first_scale_count = smoothscale.call_count
            page._draw_coin_amount(5, (150, 100), small_font)

        self.assertEqual(first_scale_count, 1)
        self.assertEqual(smoothscale.call_count, first_scale_count)
        self.assertEqual(len(page._coin_text_cache), 1)


if __name__ == "__main__":
    unittest.main()
