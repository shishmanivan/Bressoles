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

    def test_locked_empty_and_passive_slots_are_skipped_without_jumping(self):
        page = self.page([100, None, 110, 100])
        page.side_cards_locked_top[0] = True
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(set(page.side_card_jump_animations), {3})
        self.assertEqual(page.Money, 17)

    def test_unboosted_shareholder_and_rebate_do_not_jump_in_queue(self):
        page = self.page([100, 110])
        page.active_gold_cards = []
        self.assertTrue(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.side_card_jump_animations, {})
        self.assertEqual(page.lifecycle_card_jump_animations, {})
        self.assertEqual(page.Money, 10)

    def test_no_change_bankruptcy_and_blocked_extra_turn_do_not_jump(self):
        page = self.page([113, 116])
        page.Aprice = 2
        self.assertTrue(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.side_card_jump_animations, {})
        self.assertEqual(page.LastTurn, 8)

    def test_successful_extra_turn_still_jumps_and_waits(self):
        page = self.page([116, 100])
        page.boss_block_card_turn_extensions = False
        self.assertFalse(page._apply_red_card_effects_if_needed())
        self.assertEqual(page.LastTurn, 9)
        self.assertEqual(set(page.side_card_jump_animations), {0})
        self.assertEqual(page.Money, 10)


    def test_breakout_in_queue_jumps_only_when_prices_double(self):
        for roll, quantity, succeeds in ((50, 1, True), (51, 1, False), (1, 0, False)):
            with self.subTest(roll=roll, quantity=quantity):
                page = self.page([125, 100])
                page.Aquantity = page.Cquantity = quantity
                page.Bquantity = 0
                with mock.patch("gameplay_page.random.randint", return_value=roll) as draw:
                    self.assertFalse(page._apply_red_card_effects_if_needed())
                    self.assertEqual((page.Aprice, page.BPrice, page.CPrice),
                                     (14, 7, 14) if succeeds else (7, 7, 7))
                    self.assertEqual(set(page.side_card_jump_animations),
                                     {0} if succeeds else {1})
                    self.assertEqual(page.Money, 10 if succeeds else 17)
                    # Repeated updates must not reroll a resolved Breakout.
                    self.assertFalse(page._apply_red_card_effects_if_needed())
                    self.assertEqual(draw.call_count, int(quantity > 0))
                if succeeds:
                    page.side_card_jump_animations.clear()
                    self.assertFalse(page._apply_red_card_effects_if_needed())
                    self.assertEqual(set(page.side_card_jump_animations), {1})
                    self.assertEqual(page.Money, 24)


if __name__ == "__main__":
    unittest.main()
