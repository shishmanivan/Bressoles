import copy
import unittest
from types import SimpleNamespace
from unittest import mock

import game_state
from boss_logic import BOSS_LEVELS, SAY_REWARD_WEIGHTS, apply_boss_functionality, apply_say_random_reward
from gameplay_page import GameplayPage


class SayBossTests(unittest.TestCase):
    def setUp(self):
        self.original_state = {
            "napoleondors": game_state.napoleondors,
            "napoleondor_level": game_state.napoleondor_level,
            "global_hand_bonus": game_state.global_hand_bonus,
            "boss_lifecycle_slot_bonus": game_state.boss_lifecycle_slot_bonus,
            "silver_cards": copy.deepcopy(game_state.silver_cards),
            "gold_cards": copy.deepcopy(game_state.gold_cards),
        }
        game_state.napoleondors = 0
        game_state.napoleondor_level = 5
        game_state.global_hand_bonus = 0
        game_state.boss_lifecycle_slot_bonus = 0
        game_state.silver_cards = []
        game_state.gold_cards = []

    def tearDown(self):
        for name, value in self.original_state.items():
            setattr(game_state, name, value)

    def _timer_page(self):
        page = GameplayPage.__new__(GameplayPage)
        page.boss_turn_time_limit_seconds = 0
        page.boss_turn_timer_remaining_ms = 0
        page.boss_turn_timer_last_tick = 0
        page.win_lose_state = None
        page.pause_menu_active = False
        page.deck_view_active = False
        page._is_turn_resolution_active = mock.Mock(return_value=False)
        page._is_hand_transition_active = mock.Mock(return_value=False)
        page._start_turn_resolution = mock.Mock(return_value=True)
        return page

    def test_say_is_a_category_two_boss(self):
        self.assertEqual(BOSS_LEVELS["13_Say.png"], 2)

    def test_timer_counts_from_seven_and_auto_ends_at_zero(self):
        page = self._timer_page()
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=0):
            apply_boss_functionality("SevenTurnSeconds", page)

        self.assertEqual(page._get_boss_turn_timer_seconds(), 7)
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=6999):
            self.assertFalse(page._update_boss_turn_timer())
        self.assertEqual(page._get_boss_turn_timer_seconds(), 1)

        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=7000):
            self.assertTrue(page._update_boss_turn_timer())
        self.assertEqual(page._get_boss_turn_timer_seconds(), 0)
        page._start_turn_resolution.assert_called_once_with()

    def test_timer_pauses_while_pause_menu_is_open(self):
        page = self._timer_page()
        page.boss_turn_time_limit_seconds = 7
        page.boss_turn_timer_remaining_ms = 7000
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=1000):
            page._update_boss_turn_timer()
        page.pause_menu_active = True
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=6000):
            page._update_boss_turn_timer()
        page.pause_menu_active = False
        with mock.patch("gameplay_page.pygame.time.get_ticks", return_value=7000):
            page._update_boss_turn_timer()

        self.assertEqual(page.boss_turn_timer_remaining_ms, 5000)
        page._start_turn_resolution.assert_not_called()

    def test_reward_table_totals_one_hundred_with_five_more_likely_than_ten(self):
        self.assertEqual(sum(SAY_REWARD_WEIGHTS.values()), 100)
        self.assertEqual(SAY_REWARD_WEIGHTS["napoleondors_7"], 15)
        self.assertGreater(
            SAY_REWARD_WEIGHTS["napoleondors_5"],
            SAY_REWARD_WEIGHTS["napoleondors_10"],
        )
        gameplay = SimpleNamespace(level_number=5, hand=7, last_earned_cards=[])
        with mock.patch("boss_logic.random.choices", return_value=["napoleondors_5"]) as choose:
            self.assertEqual(apply_say_random_reward(gameplay), "napoleondors_5")

        choose.assert_called_once_with(
            list(SAY_REWARD_WEIGHTS),
            weights=list(SAY_REWARD_WEIGHTS.values()),
            k=1,
        )
        self.assertEqual(game_state.napoleondors, 5)

    def test_seven_napoleondor_reward(self):
        gameplay = SimpleNamespace(level_number=5, hand=7, last_earned_cards=[])
        with mock.patch("boss_logic.random.choices", return_value=["napoleondors_7"]):
            self.assertEqual(apply_say_random_reward(gameplay), "napoleondors_7")

        self.assertEqual(game_state.napoleondors, 7)

    def test_hand_and_lifecycle_slot_rewards_persist_as_boss_bonuses(self):
        gameplay = SimpleNamespace(level_number=5, hand=7, last_earned_cards=[])
        with mock.patch("boss_logic.random.choices", return_value=["hand_slot"]):
            apply_say_random_reward(gameplay)
        with mock.patch("boss_logic.random.choices", return_value=["lifecycle_slot"]):
            apply_say_random_reward(gameplay)

        self.assertEqual(gameplay.hand, 8)
        self.assertEqual(game_state.global_hand_bonus, 1)
        self.assertEqual(game_state.boss_lifecycle_slot_bonus, 1)

    def test_card_rewards_are_added_to_inventory_and_result_preview(self):
        gameplay = SimpleNamespace(level_number=5, hand=7, last_earned_cards=[])
        with (
            mock.patch("boss_logic.random.choices", return_value=["gold_card"]),
            mock.patch.object(game_state, "add_random_gold_card", return_value=401),
        ):
            apply_say_random_reward(gameplay)
        with (
            mock.patch("boss_logic.random.choices", return_value=["rare_silver_cards"]),
            mock.patch.object(game_state, "buy_underwriter_cards", return_value=[205, 209]),
        ):
            apply_say_random_reward(gameplay)

        self.assertEqual(gameplay.last_earned_cards, [401, 205, 209])


if __name__ == "__main__":
    unittest.main()
