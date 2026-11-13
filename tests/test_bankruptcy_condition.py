import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import game_state
import profile_manager
import gameplay_bankruptcy_condition as condition
from gameplay_conditions import BANKRUPTCY, LEVEL_CONDITIONS, has_active_condition
from gameplay_page import GameplayPage
from level_routes import get_campaign_content_level


class BankruptcyConditionTests(unittest.TestCase):
    def setUp(self):
        progress = profile_manager._capture_progress()
        profile = profile_manager._default_profile(1)
        profile["progress"] = progress
        self.addCleanup(profile_manager.apply_profile_to_game_state, profile)
        game_state.set_bankruptcy_condition_chance(0)

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

    def test_first_card_only_activates_five_percent(self):
        for card in (113, 114, 115, 117):
            game_state.set_bankruptcy_condition_chance(0)
            page = self.page()
            page.side_cards_top = [card]
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 5)
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 5)

    def test_fresh_cards_add_percentage_points_once_in_slot_order(self):
        page = self.page()
        page.side_cards_top = [117, 113, 117, 114, 115, 100]
        page.side_cards_locked_top = {3: True}
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 9)
        page.bankruptcy_condition_cards_counted = False
        page.side_cards_top = [114]
        page.side_cards_locked_top = {}
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 10)

    def test_cap_at_one_hundred(self):
        page = self.page()
        page.bankruptcy_condition_chance = 99
        page.side_cards_top = [117, 113]
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 100)

    def test_chance_carries_between_rounds_and_bosses(self):
        first = self.page()
        first.side_cards_top = [117, 113]
        condition.register_fresh_cards(first)
        self.assertEqual(first.bankruptcy_condition_chance, 6)
        first.bankruptcy_condition_last_roll_day = 1
        for boss_fight in (False, True, False):
            next_round = self.page()
            next_round.is_boss_fight = boss_fight
            self.assertEqual(next_round.bankruptcy_condition_chance, 6)
            self.assertIsNone(next_round.bankruptcy_condition_last_roll_day)
            self.assertFalse(next_round.bankruptcy_condition_cards_counted)
        next_round.side_cards_top = [117]
        condition.register_fresh_cards(next_round)
        self.assertEqual(next_round.bankruptcy_condition_chance, 8)

    def test_profile_persists_chance_and_old_active_save_migrates(self):
        page = self.page()
        page.side_cards_top = [113, 117]
        condition.register_fresh_cards(page)
        profile = profile_manager._default_profile(1)
        profile["progress"] = profile_manager._capture_progress()
        game_state.set_bankruptcy_condition_chance(0)
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(self.page().bankruptcy_condition_chance, 7)
        del profile["progress"]["bankruptcy_condition_chance"]
        profile_manager.apply_profile_to_game_state(profile)
        self.assertEqual(game_state.bankruptcy_condition_chance, 0)
        condition.restore(page, {"chance": 13, "last_roll_day": 4})
        self.assertEqual(game_state.bankruptcy_condition_chance, 13)
        self.assertEqual(self.page().bankruptcy_condition_chance, 13)

    def test_run_loss_restart_and_completion_reset_chance(self):
        for reset in (game_state.reset_level_attempt, game_state.complete_level_run):
            game_state.set_bankruptcy_condition_chance(27)
            reset(get_campaign_content_level(6))
            page = self.page()
            self.assertEqual(page.bankruptcy_condition_chance, 0)
            page.side_cards_top = [117]
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 5)

    def test_stake_suppression_preserves_chance_into_following_round(self):
        game_state.set_bankruptcy_condition_chance(17)
        page = self.page()
        page.active_silver_cards = [205]
        page.side_cards_top = [117]
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 17)
        self.assertEqual(self.page().bankruptcy_condition_chance, 17)

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

    def test_blue_chips_blocks_condition_price_fall_and_bankruptcy_visuals(self):
        for market in (0, 1, 2):
            with self.subTest(market=market):
                page = self.page()
                # Exercise the real Blue Chips protection with card 22 on the chosen market.
                del page._protect_blue_chip_prices
                page._protect_put_prices = lambda previous, proposed: proposed
                page.market_cards = {0: {}, 1: {}, 2: {}}
                page.market_cards[market][0] = 22
                page.bankruptcy_condition_chance = 100
                previous = (page.Aprice, page.BPrice, page.CPrice)
                with mock.patch.object(condition.random, "random", return_value=0), \
                        mock.patch.object(condition.random, "choice", return_value=market) as choose, \
                        mock.patch.object(condition.animation, "start") as animate, \
                        mock.patch.object(condition.condition_coins, "show") as coin:
                    self.assertFalse(condition.resolve_turn(page))
                    self.assertFalse(condition.resolve_turn(page))
                    choose.assert_called_once_with((0, 1, 2))
                    animate.assert_not_called()
                    coin.assert_not_called()
                self.assertEqual((page.Aprice, page.BPrice, page.CPrice), previous)
                self.assertEqual(page.bankruptcy_condition_chance, 100)

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
        self.assertEqual(restored.bankruptcy_condition_chance, 7)
        with mock.patch.object(condition.random, "random") as roll:
            self.assertFalse(condition.resolve_turn(restored))
        roll.assert_not_called()
        condition.restore(restored, {})
        self.assertEqual(restored.bankruptcy_condition_chance, 7)
        self.assertIsNone(restored.bankruptcy_condition_last_roll_day)
        self.assertFalse(restored.bankruptcy_condition_cards_counted)

    def test_assignment_is_portable_and_absence_disables_it(self):
        page = self.page()
        self.assertTrue(has_active_condition(page, BANKRUPTCY))
        page.level_number = 3
        page.side_cards_top = [117]
        condition.register_fresh_cards(page)
        self.assertEqual(page.bankruptcy_condition_chance, 0)
        with mock.patch.dict(LEVEL_CONDITIONS, {3: (BANKRUPTCY,)}):
            condition.register_fresh_cards(page)
            self.assertEqual(page.bankruptcy_condition_chance, 5)

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
        page._has_effect_animations = mock.Mock(return_value=False)
        page.side_card_jump_animations = {}
        for name in ("_apply_market_crash_effect_if_needed", "_apply_bankruptcy_effects_if_needed",
                     "_apply_manipulation_effect_if_needed", "_start_card_jump_animation"):
            setattr(page, name, mock.Mock())
        page._apply_red_card_effects_if_needed()
        page._apply_red_card_effects_if_needed()
        self.assertEqual(page.bankruptcy_condition_chance, 6)


if __name__ == "__main__":
    unittest.main()
