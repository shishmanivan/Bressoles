import os
import json
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import profile_manager
import game_state


class ProfileContractTests(unittest.TestCase):
    def test_windfall_progress_is_stored_and_restored(self):
        original = game_state.windfall_boss_victories
        try:
            game_state.windfall_boss_victories = 3
            progress = profile_manager._capture_progress()
            self.assertEqual(progress["windfall_boss_victories"], 3)

            profile = profile_manager._default_profile(1)
            profile["progress"]["windfall_boss_victories"] = 4
            profile_manager.apply_profile_to_game_state(profile)
            self.assertEqual(game_state.get_windfall_boss_victories(), 4)
        finally:
            game_state.windfall_boss_victories = original

    def test_completed_level_black_rewards_are_restored_in_existing_profiles(self):
        profile = profile_manager._default_profile(1)
        profile["progress"]["level_3_boss_defeated"] = True
        profile["progress"]["level_4_boss_defeated"] = True
        profile["progress"]["level_5_boss_defeated"] = True
        profile["progress"]["black_cards"] = [301, 303]

        self.assertTrue(profile_manager._migrate_completed_black_rewards(profile))
        self.assertEqual(profile["progress"]["black_cards"], [301, 302, 303])
        self.assertFalse(profile_manager._migrate_completed_black_rewards(profile))

    def test_campaign_v2_migrates_the_former_level4_run_to_level5(self):
        profile = {
            "version": 1,
            "progress": {
                "boss_progress": {"4": {"defeated": 2}},
                "earned_reward_cards": {"4": [100, 112]},
                "napoleondor_level": 4,
                "active_red_cards_level": 4,
            },
            "active_game": {
                "context": {"level_number": 4},
                "state": {"Day": 3},
            },
        }

        self.assertTrue(profile_manager._migrate_campaign_v2(profile))

        self.assertEqual(profile["version"], 2)
        self.assertNotIn("4", profile["progress"]["boss_progress"])
        self.assertEqual(profile["progress"]["boss_progress"]["5"]["defeated"], 2)
        self.assertEqual(profile["progress"]["earned_reward_cards"]["5"], [100, 112])
        self.assertEqual(profile["progress"]["napoleondor_level"], 5)
        self.assertEqual(profile["progress"]["active_red_cards_level"], 5)
        self.assertEqual(profile["active_game"]["context"]["level_number"], 5)

    def test_boss_progress_round_trip_preserves_route_and_active_encounter(self):
        source = {
            4: {
                "defeated": 1,
                "last_rect": pygame.Rect(100, 200, 100, 100),
                "lines": [(10, 20, 30, 40)],
                "defeated_bosses": [
                    {"filename": "7_Kolbe.png", "rect": pygame.Rect(100, 200, 100, 100)}
                ],
                "roster": [["7_Kolbe.png"], ["9_Laffitte.png"]],
                "round_progress": {
                    "1:0:9_Laffitte.png": {
                        "completed_rounds": [1],
                        "round_selections": {1: {"key": "m"}},
                        "saved_lines": [(1, 2, 3, 4)],
                    }
                },
                "current_boss": {
                    "defeated_count": 1,
                    "boss_index": 0,
                    "boss_filename": "9_Laffitte.png",
                    "clicked_boss_rect": [300, 400, 100, 100],
                    "saved_lines": [(5, 6, 7, 8)],
                },
                "reward_checkpoint": {"global_dobor": 99},
                "run_stats_started": True,
                "run_stats_finished": False,
            }
        }

        serialized = profile_manager._serialize_boss_progress(source)
        restored = profile_manager._restore_boss_progress(serialized)
        state = restored[4]

        self.assertEqual(state["defeated"], 1)
        self.assertEqual(state["last_rect"], pygame.Rect(100, 200, 100, 100))
        self.assertEqual(state["roster"], [["7_Kolbe.png"], ["9_Laffitte.png"]])
        self.assertEqual(state["current_boss"]["boss_filename"], "9_Laffitte.png")
        self.assertNotIn("reward_checkpoint", state)
        self.assertTrue(state["run_stats_started"])
        self.assertFalse(state["run_stats_finished"])
        self.assertEqual(
            state["round_progress"]["1:0:9_Laffitte.png"]["round_selections"],
            {1: {"key": "m"}},
        )

    def test_profile_write_is_atomic_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.json")
            with (
                mock.patch.object(profile_manager, "PROFILES_DIR", temp_dir),
                mock.patch.object(profile_manager, "INDEX_FILE", index_path),
            ):
                profile = profile_manager._default_profile(1)
                profile["name"] = "Atomic"
                profile_manager.save_profile(profile)

                with open(profile_manager.get_profile_path(1), "r", encoding="utf-8") as profile_file:
                    saved = json.load(profile_file)

                self.assertEqual(saved["name"], "Atomic")
                self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(temp_dir)))

    def test_failed_atomic_replace_preserves_previous_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.json")
            with (
                mock.patch.object(profile_manager, "PROFILES_DIR", temp_dir),
                mock.patch.object(profile_manager, "INDEX_FILE", index_path),
            ):
                profile = profile_manager._default_profile(1)
                profile["name"] = "Before"
                profile_manager.save_profile(profile)
                profile["name"] = "After"

                with mock.patch.object(profile_manager.os, "replace", side_effect=OSError("replace failed")):
                    with self.assertRaises(OSError):
                        profile_manager.save_profile(profile)

                with open(profile_manager.get_profile_path(1), "r", encoding="utf-8") as profile_file:
                    saved = json.load(profile_file)

                self.assertEqual(saved["name"], "Before")
                self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(temp_dir)))


if __name__ == "__main__":
    unittest.main()
