import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager as profiles


class BalanceRollbackTests(unittest.TestCase):
    def setUp(self):
        self.original = profiles._capture_progress()
        self.directory = tempfile.TemporaryDirectory()
        self.patch = patch.object(profiles, "PROFILES_DIR", self.directory.name)
        self.patch.start()
        profiles.apply_profile_to_game_state(profiles._default_profile(1))

    def tearDown(self):
        profiles.apply_profile_to_game_state({"progress": self.original})
        self.patch.stop()
        self.directory.cleanup()

    def test_repeated_replay_restores_full_boundary_and_keeps_statistics(self):
        profiles.capture_balance_checkpoint(1, 1)
        boundary = profiles._capture_progress()
        stats_path = profiles.get_stats_file(1)
        with open(stats_path, "wb") as output:
            output.write(b"attempts,3\n")
        for _ in range(3):
            game_state.level_1_boss_defeated = True
            game_state.napoleondors = 125
            game_state.shop_deck_cards = [101]
            game_state.boss_progress[1] = game_state.new_boss_progress_state()
            game_state.boss_progress[1]["run_stats_started"] = True
            profiles.save_active_game(1, {"level_number": 1}, {})
            self.assertTrue(profiles.load_profile(1)["balance_checkpoint"]["completed_progress"]["level_1_boss_defeated"])
            self.assertTrue(profiles.rollback_balance_level(1))
            self.assertEqual(profiles._capture_progress(), boundary)
            self.assertIsNone(profiles.get_active_game(1))
            profiles.capture_balance_checkpoint(1, 1)
            self.assertEqual(profiles.get_balance_replay_level(1), 1)
        with open(stats_path, "rb") as source:
            self.assertEqual(source.read(), b"attempts,3\n")

    def test_next_level_preserves_previous_victory_and_profile_isolation(self):
        profiles.capture_balance_checkpoint(1, 1)
        game_state.level_1_boss_defeated = True
        game_state.napoleondors = 42
        profiles.save_progress_from_game_state(1)
        profiles.capture_balance_checkpoint(1, 2)
        game_state.level_2_boss_defeated = True
        game_state.napoleondors = 999
        profiles.save_progress_from_game_state(1)
        self.assertIsNone(profiles.get_balance_replay_level(2))
        self.assertFalse(profiles.rollback_balance_level(2))
        profiles.rollback_balance_level(1)
        self.assertTrue(game_state.level_1_boss_defeated)
        self.assertFalse(game_state.level_2_boss_defeated)
        self.assertEqual(game_state.napoleondors, 42)

    def test_resume_does_not_replace_checkpoint(self):
        profiles.capture_balance_checkpoint(1, 2)
        game_state.napoleondors = 99
        profiles.capture_balance_checkpoint(1, 2)
        profiles.rollback_balance_level(1)
        self.assertEqual(game_state.napoleondors, 0)

    def test_legacy_run_does_not_invent_start_state(self):
        game_state.boss_progress[2] = game_state.new_boss_progress_state()
        game_state.boss_progress[2]["run_stats_started"] = True
        profiles.capture_balance_checkpoint(1, 2)
        self.assertIsNone(profiles.get_balance_replay_level(1))
