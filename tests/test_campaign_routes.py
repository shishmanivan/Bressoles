import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
from boss_logic import _ensure_level3_roster, _ensure_level4_roster
from boss_progress import complete_boss_position, remember_current_boss
from profile_manager import _restore_boss_progress, _serialize_boss_progress


class CampaignRosterTests(unittest.TestCase):
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

    def test_level4_saved_roster_requires_correct_tiers_and_no_repeats(self):
        malformed = {
            "roster": [
                ["2_AdamSmith.png", "3_RobertFulton.png"],
                ["8_List.png", "9_Laffitte.png"],
                ["2_AdamSmith.png"],
                ["9_Laffitte.png"],
            ]
        }
        replacement = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["4_NicolasApper.png"],
            ["7_Kolbe.png"],
        ]
        with mock.patch("boss_logic._generate_level4_boss_roster", return_value=copy.deepcopy(replacement)):
            roster = _ensure_level4_roster(malformed, 4)

        self.assertEqual(roster, replacement)
        self.assertEqual(malformed["roster"], replacement)

    def test_each_boss_transition_survives_a_profile_round_trip(self):
        roster = [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["8_List.png", "9_Laffitte.png"],
            ["4_NicolasApper.png"],
            ["7_Kolbe.png"],
        ]
        state = game_state.new_boss_progress_state()
        state["roster"] = copy.deepcopy(roster)
        selected_bosses = ["3_RobertFulton.png", "9_Laffitte.png", "4_NicolasApper.png", "7_Kolbe.png"]

        for defeated_count, boss_filename in enumerate(selected_bosses):
            boss_index = roster[defeated_count].index(boss_filename)
            context = remember_current_boss(state, defeated_count, boss_index, boss_filename)
            complete_boss_position(state, context)
            state = _restore_boss_progress(_serialize_boss_progress({4: state}))[4]

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
