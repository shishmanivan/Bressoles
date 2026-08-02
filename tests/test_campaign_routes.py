import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
from boss_logic import (
    BOSS_LEVELS,
    _ensure_level3_roster,
    _ensure_level5_roster,
    _generate_level5_boss_roster,
)
from boss_progress import complete_boss_position, remember_current_boss
from profile_manager import _restore_boss_progress, _serialize_boss_progress


class CampaignRosterTests(unittest.TestCase):
    def test_level5_generates_two_choices_for_each_category_position(self):
        roster = _generate_level5_boss_roster(4)

        self.assertEqual(len(roster), 4)
        self.assertTrue(all(len(step) == 2 for step in roster))
        first_category_choices = roster[0] + roster[1]
        second_category_choices = roster[2] + roster[3]
        self.assertEqual(len(first_category_choices), len(set(first_category_choices)))
        self.assertEqual(len(second_category_choices), len(set(second_category_choices)))
        self.assertTrue(all(BOSS_LEVELS[filename] == 1 for filename in first_category_choices))
        self.assertTrue(all(BOSS_LEVELS[filename] == 2 for filename in second_category_choices))

    def test_level3_saved_roster_requires_three_distinct_single_boss_steps(self):
        malformed = {
            "roster": [
                ["2_AdamSmith.png"],
                ["2_AdamSmith.png"],
                ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ]
        }
        replacement = [
            ["2_AdamSmith.png"],
            ["4_NicolasApper.png"],
            ["6_Arkwright.png"],
        ]
        with mock.patch("boss_logic._generate_level3_boss_roster", return_value=copy.deepcopy(replacement)):
            roster = _ensure_level3_roster(malformed, 3)

        self.assertEqual(roster, replacement)
        self.assertEqual(malformed["roster"], replacement)

    def test_level5_saved_roster_requires_correct_tiers_and_no_repeats(self):
        malformed = {
            "roster": [
                ["2_AdamSmith.png", "3_RobertFulton.png"],
                ["3_RobertFulton.png", "5_SamuelSlater.png"],
                ["8_List.png", "9_Laffitte.png"],
                ["9_Laffitte.png", "11_Malthus.png"],
            ]
        }
        replacement = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["11_Malthus.png", "12_Ricardo.png"],
        ]
        with mock.patch("boss_logic._generate_level5_boss_roster", return_value=copy.deepcopy(replacement)):
            roster = _ensure_level5_roster(malformed, 4)

        self.assertEqual(roster, replacement)
        self.assertEqual(malformed["roster"], replacement)

    def test_level5_replaces_a_roster_using_the_old_category_order(self):
        malformed = {
            "roster": [
                ["2_AdamSmith.png", "3_RobertFulton.png"],
                ["8_List.png", "11_Malthus.png"],
                ["4_NicolasApper.png"],
                ["7_Kolbe.png"],
            ]
        }

        replacement = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["11_Malthus.png", "12_Ricardo.png"],
        ]
        with mock.patch("boss_logic._generate_level5_boss_roster", return_value=copy.deepcopy(replacement)):
            roster = _ensure_level5_roster(malformed, 4)

        self.assertEqual(roster, replacement)

    def test_each_boss_transition_survives_a_profile_round_trip(self):
        roster = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["11_Malthus.png", "12_Ricardo.png"],
        ]
        state = game_state.new_boss_progress_state()
        state["roster"] = copy.deepcopy(roster)
        selected_bosses = [
            "3_RobertFulton.png",
            "4_NicolasApper.png",
            "9_Laffitte.png",
            "12_Ricardo.png",
        ]

        for defeated_count, boss_filename in enumerate(selected_bosses):
            boss_index = roster[defeated_count].index(boss_filename)
            context = remember_current_boss(state, defeated_count, boss_index, boss_filename)
            complete_boss_position(state, context)
            state = _restore_boss_progress(_serialize_boss_progress({5: state}))[5]

            self.assertEqual(state["defeated"], defeated_count + 1)
            self.assertIsNone(state["current_boss"])
            self.assertEqual(state["roster"], roster)

        self.assertEqual(
            [entry["filename"] for entry in state["defeated_bosses"]],
            selected_bosses,
        )
        self.assertEqual(state["round_progress"], {})


if __name__ == "__main__":
    unittest.main()
