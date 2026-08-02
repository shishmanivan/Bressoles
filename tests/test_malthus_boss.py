import unittest
from unittest import mock

import game_state
import profile_manager
from boss_logic import (
    BOSS_LEVELS,
    _generate_level5_boss_roster,
    apply_boss_functionality,
    apply_boss_reward,
)
from gameplay_page import GameplayPage


class MalthusBossTests(unittest.TestCase):
    def setUp(self):
        self.original_slot_bonus = game_state.boss_lifecycle_slot_bonus
        self.original_issuer_count = game_state.issuer_bought_count
        self.original_frugality = game_state.Frugality
        game_state.boss_lifecycle_slot_bonus = 0
        game_state.issuer_bought_count = 0
        game_state.Frugality = 0

    def tearDown(self):
        game_state.boss_lifecycle_slot_bonus = self.original_slot_bonus
        game_state.issuer_bought_count = self.original_issuer_count
        game_state.Frugality = self.original_frugality

    def test_malthus_is_a_category_two_boss_offered_in_the_final_two_steps(self):
        self.assertEqual(BOSS_LEVELS["11_Malthus.png"], 2)
        with mock.patch("boss_logic.random.shuffle", side_effect=lambda values: None):
            roster = _generate_level5_boss_roster(4)

        category_two_choices = roster[2] + roster[3]
        self.assertIn("11_Malthus.png", category_two_choices)
        self.assertEqual(len(category_two_choices), 4)
        self.assertEqual(len(set(category_two_choices)), 4)
        self.assertTrue(
            set(category_two_choices).issubset(
                {
                    "8_List.png",
                    "9_Laffitte.png",
                    "11_Malthus.png",
                    "12_Ricardo.png",
                    "13_Say.png",
                    "14_Peabody.png",
                }
            )
        )

    def test_card_turn_extensions_are_blocked_but_prior_boss_bonus_remains(self):
        page = GameplayPage.__new__(GameplayPage)
        page.LastTurn = 10  # Base 8 turns plus Samuel Slater's boss reward.
        page.boss_block_card_turn_extensions = False
        apply_boss_functionality("BlockCardTurnExtensions", page)

        page._active_lifecycle_cards = mock.Mock(return_value=[202, 203, 301])
        self.assertEqual(page._apply_silver_last_turn_bonuses(), 0)
        self.assertEqual(page.LastTurn, 10)

        game_state.Frugality = 4
        page._initial_saved_state = None
        self.assertEqual(page._apply_frugality_turn_bonus(), 0)
        self.assertEqual(game_state.Frugality, 0)
        self.assertEqual(page.LastTurn, 10)

        page._count_fresh_side_card = mock.Mock(return_value=1)
        self.assertFalse(page._apply_extra_turn_effect_if_needed())
        self.assertFalse(page._apply_forward_trading_effect_if_needed())
        self.assertEqual(page.LastTurn, 10)

    def test_reward_adds_a_shared_slot_and_is_saved(self):
        gameplay = mock.Mock()
        apply_boss_reward("LifecycleSlotPlus1", gameplay)

        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 4)
        progress = profile_manager._capture_progress()
        self.assertEqual(progress["boss_lifecycle_slot_bonus"], 1)

    def test_reward_slot_is_removed_after_defeat(self):
        game_state.boss_lifecycle_slot_bonus = 1
        game_state.issuer_bought_count = 1

        game_state.reset_level_attempt(5)

        self.assertEqual(game_state.boss_lifecycle_slot_bonus, 0)
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), game_state.LIFECYCLE_CARD_BASE_SLOTS)


if __name__ == "__main__":
    unittest.main()
