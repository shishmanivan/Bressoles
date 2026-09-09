import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import asset_loaders
import boss_page
import gameplay_assets
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

    def test_image_variants_match_individual_scaling_with_one_decode(self):
        path = os.path.join("Cards", "Arts", "Negative.png")
        sizes = ((142, 244), (99, 171), (84, 145))
        expected = {size: pygame.image.tostring(
            asset_loaders.load_scaled_image(path, target_size=size), "RGBA",
        ) for size in sizes}
        asset_loaders._scaled_image_cache.clear()
        with mock.patch.object(pygame.image, "load", wraps=pygame.image.load) as image_load:
            variants = asset_loaders.load_scaled_image_variants(path, sizes)
            self.assertEqual(image_load.call_count, 1)
            for size in sizes:
                self.assertEqual(variants[size].get_size(), size)
                self.assertEqual(pygame.image.tostring(variants[size], "RGBA"), expected[size])
                self.assertIs(asset_loaders.load_scaled_image(path, target_size=size), variants[size])
            again = asset_loaders.load_scaled_image_variants(path, sizes)
            self.assertEqual(image_load.call_count, 1)
            self.assertIsNot(again, variants)
            self.assertTrue(all(again[size] is variants[size] for size in sizes))

    def test_image_variants_fill_only_missing_sizes_and_preserve_missing_file_fallback(self):
        path = os.path.join("Cards", "Arts", "Negative.png")
        sizes = ((142, 244), (99, 171), (84, 145))
        existing = asset_loaders.load_scaled_image(path, target_size=sizes[0])
        with mock.patch.object(pygame.image, "load", wraps=pygame.image.load) as image_load:
            variants = asset_loaders.load_scaled_image_variants(path, sizes + (sizes[1],))
            self.assertIs(variants[sizes[0]], existing)
            self.assertEqual(image_load.call_count, 1)
            with mock.patch.object(asset_loaders.os.path, "exists", return_value=False):
                self.assertEqual(asset_loaders.load_scaled_image_variants(path, sizes), dict.fromkeys(sizes))
            self.assertEqual(image_load.call_count, 1)

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

    def test_selected_card_originals_preserve_scaled_pixels_and_bid_labels(self):
        source = pygame.Surface((200, 320), pygame.SRCALPHA)
        source.fill((240, 220, 180, 255))
        pygame.draw.rect(source, (100, 50, 20, 128), (12, 20, 80, 100))
        types = {11: 1, 12: 1, 118: 2, 119: 2, 201: 3}
        sizes = ((142, 244), (99, 171), (84, 145))
        requested = {12, 119, 201}
        with (
            mock.patch.object(gameplay_assets, "_gameplay_card_assets_cache", {}),
            mock.patch.object(gameplay_assets.os.path, "exists", return_value=True),
            mock.patch.object(pygame.image, "load", return_value=source),
        ):
            full = gameplay_assets.load_gameplay_card_assets(types, *sizes)
            selected = gameplay_assets.load_gameplay_card_assets(types, *sizes, original_card_ids=requested)

        self.assertEqual(
            {cid for cid, image in selected["card_images_original"].items() if image is not None},
            requested,
        )
        for key in ("card_images_bottom", "card_images_market", "card_images_side"):
            self.assertEqual(full[key].keys(), selected[key].keys())
            for card_id, expected in full[key].items():
                with self.subTest(key=key, card_id=card_id):
                    actual = selected[key][card_id]
                    self.assertEqual(actual.get_size(), expected.get_size())
                    self.assertEqual(pygame.image.tostring(actual, "RGBA"), pygame.image.tostring(expected, "RGBA"))
        for card_id in requested:
            self.assertEqual(
                pygame.image.tostring(selected["card_images_original"][card_id], "RGBA"),
                pygame.image.tostring(full["card_images_original"][card_id], "RGBA"),
            )
        self.assertIs(selected["card_images_market"][11], selected["card_images_market"][12])
        self.assertNotEqual(
            pygame.image.tostring(selected["card_images_bottom"][118], "RGBA"),
            pygame.image.tostring(selected["card_images_bottom"][119], "RGBA"),
        )

    def test_original_selection_is_cached_without_sharing_mutable_card_state(self):
        source = pygame.Surface((200, 320), pygame.SRCALPHA)
        args = ({11: 1, 12: 1, 201: 3}, (142, 244), (99, 171), (84, 145))
        with (
            mock.patch.object(gameplay_assets, "_gameplay_card_assets_cache", {}),
            mock.patch.object(gameplay_assets.os.path, "exists", return_value=True),
            mock.patch.object(pygame.image, "load", return_value=source) as image_load,
        ):
            first = gameplay_assets.load_gameplay_card_assets(*args, original_card_ids={201})
            loads = image_load.call_count
            second = gameplay_assets.load_gameplay_card_assets(*args, original_card_ids=[201])
            self.assertEqual(image_load.call_count, loads)
            self.assertIs(first["card_images_original"][201], second["card_images_original"][201])
            first["card_images_original"].clear()
            first["card_actions"][11] = 99
            first["card_turns"][11] = 99
            self.assertIsNotNone(second["card_images_original"][201])
            self.assertEqual(second["card_actions"][11], 2)
            self.assertEqual(second["card_turns"][11], 1)

            no_originals = gameplay_assets.load_gameplay_card_assets(*args, original_card_ids=set())
            self.assertTrue(all(image is None for image in no_originals["card_images_original"].values()))
            full = gameplay_assets.load_gameplay_card_assets(*args)
            self.assertIsNotNone(full["card_images_original"][11])
            self.assertIsNotNone(full["card_images_original"][201])


if __name__ == "__main__":
    unittest.main()
