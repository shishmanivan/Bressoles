import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import unittest
from types import SimpleNamespace
from unittest import mock
import native_render as pygame
import gameplay_parity_animation as animation
from gameplay_animation_clock import shift_animation_clocks
from tests import test_red_card_effects as red_tests


class ParityAnimationTests(unittest.TestCase):
    def test_copies_start_on_prices_grow_fade_and_leave_original_unchanged(self):
        original = pygame.Surface((20, 30), pygame.SRCALPHA)
        original.fill((30, 20, 10, 255))
        rect = original.get_rect(topleft=(100, 200))
        page = SimpleNamespace(screen=mock.Mock(), parity_animation={'elapsed': 0})
        labels = [(original, rect)] * 3
        animation.draw(page, labels)
        self.assertEqual(page.screen.blit.call_count, 3)
        image, destination = page.screen.blit.call_args.args
        self.assertEqual(destination, rect)
        self.assertEqual(image.get_size(), original.get_size())
        page.parity_animation['elapsed'] = 275
        animation.draw(page, labels)
        image, destination = page.screen.blit.call_args.args
        self.assertGreater(image.get_width(), original.get_width())
        self.assertLess(image.get_alpha(), 255)
        self.assertLess(destination.centery, rect.centery)
        self.assertEqual(original.get_alpha(), 255)
        self.assertEqual(original.get_at((0, 0)), (30, 20, 10, 255))

    def test_pause_and_red_queue_wait_for_price_copies_to_disappear(self):
        page = red_tests.RedCardEffectTests._page()
        page.side_cards_top[:2] = [123, 118]
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page._start_card_jump_animation = mock.Mock()
        with mock.patch.object(pygame.time, 'get_ticks', return_value=1000):
            self.assertTrue(page._apply_price_setting_red_card_effects_in_slot_order())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (20, 20, 20))
        shift_animation_clocks(page, 2000)
        with mock.patch.object(pygame.time, 'get_ticks', return_value=3549):
            animation.update(page)
        self.assertFalse(page._apply_price_setting_red_card_effects_in_slot_order())
        self.assertEqual(page.Aprice, 20)
        with mock.patch.object(pygame.time, 'get_ticks', return_value=3550):
            animation.update(page)
        self.assertIsNone(page.parity_animation)
        self.assertTrue(page._apply_price_setting_red_card_effects_in_slot_order())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 10, 10))
