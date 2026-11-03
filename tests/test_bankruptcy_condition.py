import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import gameplay_bankruptcy_condition as condition
from gameplay_conditions import BANKRUPTCY, LEVEL_CONDITIONS, has_active_condition
from gameplay_page import GameplayPage
from level_routes import get_campaign_content_level


class BankruptcyConditionTests(unittest.TestCase):
    def page(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = get_campaign_content_level(6)
        page.active_silver_cards = []
        page.active_gold_cards = []
        page.side_cards_top = []
        page.side_cards_locked_top = {}
        page.Day = 1
        page.win_lose_state = None
        page.turn_resolution_active = True
        page.Aprice, page.BPrice, page.CPrice = 14, 18, 26
        page._protect_blue_chip_prices = lambda old, proposed: proposed
        page._record_rebate_a_fall = mock.Mock()
        page._record_short_seller_falls = mock.Mock()
        page._record_c_price_fall = mock.Mock()
        condition.restore(page, {})
        return page

    def test_first_card_only_activates_ten_percent(self):
        for card in (113, 114, 115, 117):
            page = self.page()
            page.side_cards_top = [card]
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 10)
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 10)

    def test_fresh_cards_add_percentage_points_once_in_slot_order(self):
        page = self.page()
        page.side_cards_top = [117, 113, 117, 114, 115, 100]
        page.side_cards_locked_top = {3: True}
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 14)
        page.bankruptcy_condition_cards_counted = False
        page.side_cards_top = [114]
        page.side_cards_locked_top = {}
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 15)

    def test_cap_at_one_hundred(self):
        page = self.page()
        page.bankruptcy_condition_chance = 99
        page.side_cards_top = [117, 113]
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 100)

    def test_no_roll_before_activation(self):
        page = self.page()
        with mock.patch.object(condition.random, "random") as roll:
            self.assertFalse(condition.resolve_turn(page))
        roll.assert_not_called()

    def test_one_random_market_and_normal_animation_once_per_turn(self):
        page = self.page()
        page.bankruptcy_condition_chance = 10
        with mock.patch.object(condition.random, "random", return_value=0.09) as roll, \
                mock.patch.object(condition.random, "choice", return_value=1) as choose, \
                mock.patch.object(condition.animation, "start") as animate:
            self.assertTrue(condition.resolve_turn(page))
            self.assertFalse(condition.resolve_turn(page))
            roll.assert_called_once()
            choose.assert_called_once_with((0, 1, 2))
            animate.assert_called_once_with(page, 1)
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (14, 2, 26))
        self.assertEqual(page.bankruptcy_condition_chance, 10)

    def test_failed_roll_does_not_retry_until_next_turn(self):
        page = self.page()
        page.bankruptcy_condition_chance = 10
        with mock.patch.object(condition.random, "random", return_value=0.1) as roll:
            self.assertFalse(condition.resolve_turn(page))
            self.assertFalse(condition.resolve_turn(page))
            page.Day += 1
            self.assertFalse(condition.resolve_turn(page))
            self.assertEqual(roll.call_count, 2)

    def test_stakes_disable_activation_and_rolls(self):
        for attr, card in (("active_silver_cards", 205), ("active_gold_cards", 436)):
            page = self.page()
            setattr(page, attr, [card])
            page.side_cards_top = [117]
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 0)
            page.bankruptcy_condition_chance = 100
            with mock.patch.object(condition.random, "random") as roll:
                self.assertFalse(condition.resolve_turn(page))
            roll.assert_not_called()

    def test_state_survives_reload_without_duplicate_roll_or_card_count(self):
        page = self.page()
        page.side_cards_top = [113, 117]
        condition.register_fresh_cards(page)
        with mock.patch.object(condition.random, "random", return_value=0.9):
            condition.resolve_turn(page)
        restored = self.page()
        restored.side_cards_top = page.side_cards_top[:]
        condition.restore(restored, condition.serialize(page))
        condition.register_fresh_cards(restored)
        self.assertEqual(restored.bankruptcy_condition_chance, 12)
        with mock.patch.object(condition.random, "random") as roll:
            self.assertFalse(condition.resolve_turn(restored))
        roll.assert_not_called()
        condition.restore(restored, {})
        self.assertEqual(restored.bankruptcy_condition_chance, 0)

    def test_assignment_is_portable_and_absence_disables_it(self):
        page = self.page()
        self.assertTrue(has_active_condition(page, BANKRUPTCY))
        page.level_number = 3
        page.side_cards_top = [117]
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 0)
        with mock.patch.dict(LEVEL_CONDITIONS, {3: (BANKRUPTCY,)}):
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 10)

    def test_turn_finalization_waits_for_animation_and_never_rolls_twice(self):
        page = self.page()
        page.bankruptcy_condition_chance = 100
        page.red_effects_applied_this_resolution = True
        page.continuation_applied_this_resolution = True
        page.bankruptcy_animations = {}
        page._has_effect_animations = lambda: bool(page.bankruptcy_animations)
        page._finalize_turn_resolution = mock.Mock()
        def animate(p, market):
            p.bankruptcy_animations[market] = {}
        with mock.patch.object(condition.random, "random", return_value=0) as roll, \
                mock.patch.object(condition.animation, "start", side_effect=animate):
            page._begin_effect_finalize_or_wait()
            page._begin_effect_finalize_or_wait()
            page._finalize_turn_resolution.assert_not_called()
            page.bankruptcy_animations.clear()
            page._begin_effect_finalize_or_wait()
            page._finalize_turn_resolution.assert_called_once()
            roll.assert_called_once()

    def test_red_effect_pipeline_registers_new_cards_only_once(self):
        page = self.page()
        page.side_cards_top = [117, 114]
        for name in ("_apply_shareholder_value_effect_if_needed", "_apply_forward_trading_effect_if_needed",
                     "_apply_extended_gain_drop_effect_if_needed", "_apply_price_setting_red_card_effects_in_slot_order",
                     "_apply_extra_turn_effect_if_needed", "_apply_manipulation_effect_if_needed",
                     "_apply_deleverage_effect_if_needed"):
            setattr(page, name, mock.Mock())
        page._apply_red_card_effects_if_needed()
        page._apply_red_card_effects_if_needed()
        self.assertEqual(page.bankruptcy_condition_chance, 11)


if __name__ == "__main__":
    unittest.main()
