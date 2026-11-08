import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import native_render as pygame
from shop_page import ShopPage


class ShopAnimationTests(unittest.TestCase):
    def test_hover_click_survives_purchase_and_reentry(self):
        page = self.make_page()
        page._offer_animation = None
        page.sold_offer_indexes = set()
        page.card_hover_sound = Mock()
        page.mouse_pos = Mock(return_value=(450, 400))
        page._update_offer_hover_sound()
        page._update_offer_hover_sound()
        self.assertEqual(page.card_hover_sound.play.call_count, 1)
        page.sold_offer_indexes.add(0)
        page._update_offer_hover_sound()
        page.mouse_pos.return_value = (850, 400)
        page._update_offer_hover_sound()
        self.assertEqual(page.card_hover_sound.play.call_count, 2)
        page.mouse_pos.return_value = (100, 100)
        page._update_offer_hover_sound()
        page.mouse_pos.return_value = (850, 400)
        page._update_offer_hover_sound()
        self.assertEqual(page.card_hover_sound.play.call_count, 3)

    def make_page(self):
        page = ShopPage.__new__(ShopPage)
        page.screen = pygame.Surface((1680, 1050), pygame.SRCALPHA)
        page.panel_rect = pygame.Rect(120, 75, 1440, 900)
        page.offers = [{"kind": "card"}, {"kind": "investment"}]
        page.offer_rects = [pygame.Rect(400, 340, 176, 380), pygame.Rect(800, 340, 176, 380)]
        page.offer_drop_sound = Mock()
        page._offer_image = Mock(return_value=None)
        page.offer_image_box = (176, 296)
        page._draw_offer = Mock()
        page._offer_animation = {
            "started": None, "outgoing": [], "incoming": [0, 1], "sounded": set(),
        }
        return page

    def draw_at(self, page, tick):
        with patch("shop_page.pygame.time.get_ticks", return_value=tick):
            page._draw_animated_offers()

    def test_stagger_contact_sound_and_interaction(self):
        page = self.make_page()
        self.draw_at(page, 0)
        self.assertEqual(page._draw_offer.call_count, 1)
        self.assertFalse(page._draw_offer.call_args.kwargs["show_details"])
        self.assertEqual(page.offer_drop_sound.play.call_count, 0)
        self.assertIsNone(page._offer_at((450, 400)))
        self.draw_at(page, 199)
        self.assertEqual(page._draw_offer.call_count, 2)
        self.draw_at(page, 200)
        self.assertEqual(page._draw_offer.call_count, 4)
        self.draw_at(page, 338)
        self.assertEqual(page.offer_drop_sound.play.call_count, 1)
        first = [call for call in page._draw_offer.call_args_list if call.args[0] == 0][-1]
        self.assertTrue(first.kwargs["show_details"])
        self.assertEqual(first.args[2], page.offer_rects[0])
        self.draw_at(page, 500)
        self.assertEqual(page.offer_drop_sound.play.call_count, 1)
        self.draw_at(page, 538)
        self.assertEqual(page.offer_drop_sound.play.call_count, 2)
        self.draw_at(page, 650)
        self.assertIsNone(page._offer_animation)
        self.assertEqual(page._offer_at((450, 400)), 0)
        self.draw_at(page, 900)
        self.assertEqual(page.offer_drop_sound.play.call_count, 2)

    def test_cards_are_clipped_to_the_inner_shop_and_clip_is_restored(self):
        page = self.make_page()
        original_clip = page.screen.get_clip()
        observed_clips = []
        def draw(index, offer, rect, *, image_offset_y=0, show_details=True):
            observed_clips.append(page.screen.get_clip())
            page.screen.fill((255, 0, 0), rect.move(0, image_offset_y))
        page._draw_offer = draw
        self.draw_at(page, 0)
        self.draw_at(page, 250)
        self.assertTrue(all(c == page.panel_rect.inflate(-64, -76) for c in observed_clips))
        self.assertEqual(page.screen.get_clip(), original_clip)
        self.assertEqual(page.screen.get_at((450, 100)).a, 0)
        self.assertNotEqual(page.screen.get_at((450, 200)).a, 0)

    def test_old_large_tile_leaves_before_two_smaller_tiles_return(self):
        page = self.make_page()
        old_offer = page.offers[0]
        page.offers = [old_offer]
        old_rect = pygame.Rect(600, 340, 200, 380)
        old_tile = pygame.Surface((212, 380), pygame.SRCALPHA)
        previous = {id(old_offer): (old_tile, old_rect, (200, 296))}
        page.offers.append({"kind": "card"})
        page.offer_rects = [pygame.Rect(500, 340, 142, 380), pygame.Rect(660, 340, 142, 380)]
        page._offer_image = Mock(return_value=pygame.Surface((136, 244)))
        page._animate_offer_layout(previous)
        self.assertEqual(len(page._offer_animation["outgoing"]), 1)
        self.draw_at(page, 0)
        self.draw_at(page, 219)
        page._draw_offer.assert_not_called()
        self.draw_at(page, 220)
        self.assertEqual(page._draw_offer.call_count, 1)
        self.draw_at(page, 420)
        self.assertEqual(page._draw_offer.call_count, 3)
        self.draw_at(page, 870)
        self.assertIsNone(page._offer_animation)
        self.assertEqual(page.offer_drop_sound.play.call_count, 2)

    def test_layout_restores_full_size_after_a_smaller_assortment(self):
        page = self.make_page()
        page.offers = [{"kind": "special"} for _ in range(8)]
        page._build_offer_rects()
        self.assertLess(page.offer_image_box[0], 200)
        page.offers = page.offers[:3]
        page._build_offer_rects()
        self.assertEqual(page.offer_image_box, (200, 296))
        self.assertEqual(page.card_offer_size, (142, 244))


if __name__ == "__main__":
    unittest.main()
