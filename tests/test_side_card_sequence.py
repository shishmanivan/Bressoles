import unittest
from unittest import mock

import gameplay_bankruptcy_animation as bankruptcy
from tests import test_red_card_effects


class SideCardSequenceTests(unittest.TestCase):
    def page(self, cards):
        page = test_red_card_effects.RedCardEffectTests._page()
        page.side_cards_top[:len(cards)] = cards
        page.Aprice = page.BPrice = page.CPrice = 7
        page.Money = 10
        page.LastTurn = 8
        page.active_gold_cards = [439]
        page.boss_block_card_turn_extensions = True
        return page

    def test_bankruptcy_waits_to_last_frame_before_shareholder(self):
        page = self.page([113, 100])
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=1000):
            self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 10)
        with mock.patch("gameplay_page.pygame.time.get_ticks",
                        return_value=1000 + bankruptcy.DURATION_MS - 1):
            page.update_side_card_jump_animations()
            bankruptcy.update(page)
            self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 10)
        with mock.patch("gameplay_page.pygame.time.get_ticks",
                        return_value=1000 + bankruptcy.DURATION_MS):
            bankruptcy.update(page)
            self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 17)
        self.assertEqual(set(page.side_card_jump_animations), {1})

    def test_four_cards_wait_for_source_and_gold_animation_without_replay(self):
        page = self.page([100, 115, 100, 100])
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 17)
        page.side_card_jump_animations.clear()
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.CPrice, 7)
        page.lifecycle_card_jump_animations.clear()
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.CPrice, 2)
        self.assertEqual(page.Money, 17)
        page.bankruptcy_animations.clear()
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 17)
        page.side_card_jump_animations.clear()
        for expected, slot in ((19, 2), (21, 3)):
            self.assertFalse(page._apply_red_card_effects_if_needed())
            self.assertEqual(page.Money, expected)
            self.assertEqual(set(page.side_card_jump_animations), {slot})
            self.assertFalse(page._apply_red_card_effects_if_needed())
            self.assertEqual(page.Money, expected)
            page.side_card_jump_animations.clear()
            page.lifecycle_card_jump_animations.clear()
        self.assertTrue(page._apply_red_card_effects_if_needed())
        self.assertTrue(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 21)

    def test_locked_and_empty_slots_are_skipped_and_passive_cards_wait(self):
        page = self.page([100, None, 110, 100])
        page.side_cards_locked_top[0] = True
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(set(page.side_card_jump_animations), {2})
        self.assertEqual(page.Money, 10)
        self.assertFalse(page._apply_red_card_effects_if_needed())
        page.side_card_jump_animations.clear()
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.Money, 17)


if __name__ == "__main__":
    unittest.main()
