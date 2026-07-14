import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
import gameplay_winlose
from gameplay_winlose import apply_win_reward


POOL_STATE_FIELDS = (
    "level_1_boss_defeated",
    "level_2_boss_defeated",
    "level_3_boss_defeated",
    "earned_reward_cards",
    "round_reward_cards",
    "forced_start_hand_cards_by_level",
    "active_red_cards_level",
    "active_red_cards_deck",
    "active_silver_cards_level",
    "active_silver_cards_deck",
    "silver_cards",
    "licensed_card_ids",
)


class RewardPoolTestCase(unittest.TestCase):
    def setUp(self):
        self._snapshot = {
            field: copy.deepcopy(getattr(game_state, field))
            for field in POOL_STATE_FIELDS
        }
        game_state.level_1_boss_defeated = False
        game_state.level_2_boss_defeated = False
        game_state.level_3_boss_defeated = False
        game_state.earned_reward_cards = {}
        game_state.round_reward_cards = {}
        game_state.forced_start_hand_cards_by_level = {}
        game_state.active_red_cards_level = None
        game_state.active_red_cards_deck = []
        game_state.active_silver_cards_level = None
        game_state.active_silver_cards_deck = []
        game_state.silver_cards = []
        game_state.licensed_card_ids = set(game_state.DEFAULT_LICENSED_CARDS)

    def tearDown(self):
        for field, value in self._snapshot.items():
            setattr(game_state, field, value)


class RedRewardPoolTests(RewardPoolTestCase):
    def test_red_pool_excludes_owned_cards_and_draws_without_replacement(self):
        game_state.earned_reward_cards[4] = [111, 113]
        game_state.round_reward_cards[4] = [112]

        with (
            mock.patch.object(
                game_state,
                "build_red_cards_deck_for_level",
                return_value=[110, 111, 112, 113],
            ),
            mock.patch.object(game_state.random, "shuffle"),
        ):
            self.assertEqual(game_state.start_red_cards_deck_for_level(4), [110])

        self.assertEqual(game_state.draw_red_card_for_level(4), 110)
        self.assertIsNone(game_state.draw_red_card_for_level(4))
        self.assertEqual(game_state.active_red_cards_deck, [])

    def test_red_variable_is_an_inclusion_roll_not_a_draw_weight(self):
        cards = {
            110: {"Type": 2, "Open": 1, "Variable": 100},
            113: {"Type": 2, "Open": 1, "Variable": 50},
            122: {"Type": 2, "Open": 1, "Variable": 2},
        }
        game_state.licensed_card_ids.update(cards)

        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state.random, "randint", side_effect=[51, 2]),
        ):
            pool = game_state.build_red_cards_deck_for_level(4)

        self.assertEqual(pool, [110, 122])


class SilverRewardPoolTests(RewardPoolTestCase):
    def test_silver_pool_stays_stable_and_draws_with_replacement(self):
        with (
            mock.patch.object(game_state, "build_silver_cards_pool", return_value=[201, 204]),
            mock.patch.object(game_state.random, "shuffle"),
        ):
            game_state.start_silver_cards_deck_for_level(3)

        with (
            mock.patch.object(game_state, "build_open_silver_cards_pool", return_value=[201, 204]),
            mock.patch.object(game_state, "build_guaranteed_silver_cards_pool", return_value=[201]),
            mock.patch.object(game_state.random, "choice", return_value=204),
        ):
            self.assertEqual(game_state.draw_silver_card_for_level(3), 204)
            self.assertEqual(game_state.draw_silver_card_for_level(3), 204)

        self.assertEqual(game_state.active_silver_cards_deck, [201, 204])

    def test_valid_saved_silver_pool_is_not_rerolled(self):
        game_state.active_silver_cards_level = 3
        game_state.active_silver_cards_deck = [201, 204]

        with (
            mock.patch.object(game_state, "build_open_silver_cards_pool", return_value=[201, 204, 206]),
            mock.patch.object(game_state, "build_guaranteed_silver_cards_pool", return_value=[201]),
            mock.patch.object(game_state, "start_silver_cards_deck_for_level") as reroll,
        ):
            self.assertEqual(game_state.ensure_silver_cards_deck_for_level(3), [201, 204])

        reroll.assert_not_called()

    def test_full_silver_inventory_does_not_cancel_later_reward(self):
        game_state.silver_cards = [201] * game_state.MAX_SILVER_CARDS
        gameplay = mock.Mock()
        gameplay.is_boss_fight = False
        gameplay.level_number = 3
        gameplay.round_num = 3
        gameplay.difficulty = "m"
        gameplay.last_earned_cards = []
        temporary_cards = {}

        apply_win_reward(
            gameplay,
            earned_reward_cards=temporary_cards,
            rewards={(3, 3, "M"): {"reward1": [-1002], "reward2": [100]}},
            reward_token_random_red=-1001,
            load_boss_rewards=mock.Mock(),
            get_boss_number_from_index=mock.Mock(),
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=game_state.add_silver_card,
        )

        self.assertEqual(temporary_cards, {3: [100]})
        self.assertEqual(gameplay.last_earned_cards, [100])


class RewardSelectionTests(RewardPoolTestCase):
    def test_gain_drop_reward_lists_use_the_declared_weights(self):
        with mock.patch.object(
            gameplay_winlose.random,
            "choices",
            return_value=[15],
        ) as choose:
            selected = gameplay_winlose._choose_reward_card([11, 12, 15, 16])

        self.assertEqual(selected, 15)
        choose.assert_called_once_with(
            [11, 12, 15, 16],
            weights=[25, 25, 20, 10],
            k=1,
        )

    def test_profile_round_trip_preserves_both_rolled_pools(self):
        game_state.active_red_cards_level = 4
        game_state.active_red_cards_deck = [121, 118]
        game_state.active_silver_cards_level = 4
        game_state.active_silver_cards_deck = [201, 203, 220]
        progress = profile_manager._capture_progress()

        game_state.active_red_cards_level = None
        game_state.active_red_cards_deck = []
        game_state.active_silver_cards_level = None
        game_state.active_silver_cards_deck = []
        profile_manager.apply_profile_to_game_state({"progress": progress})

        self.assertEqual(game_state.active_red_cards_level, 4)
        self.assertEqual(game_state.active_red_cards_deck, [121, 118])
        self.assertEqual(game_state.active_silver_cards_level, 4)
        self.assertEqual(game_state.active_silver_cards_deck, [201, 203, 220])


if __name__ == "__main__":
    unittest.main()
