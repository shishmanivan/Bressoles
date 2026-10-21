import tempfile
import unittest
from unittest.mock import patch

import profile_manager
from player_time_stats import empty_stats, record


class PlayerTimeStatsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(profile_manager, "PROFILES_DIR", directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        profile_manager.save_profile(profile_manager._default_profile(1))

    def test_new_profile_records_round_time_once_and_groups_by_level(self):
        profile_manager.record_player_time(1, 2, "one", 12.5)
        profile_manager.record_player_time(1, 2, "one", 99)
        profile_manager.record_player_time(1, 2, "two", 7.5)
        stats = profile_manager.load_profile(1)["play_time_stats"]
        self.assertEqual(stats["total_seconds"], 20)
        self.assertEqual(stats["levels"]["2"], {"seconds": 20, "rounds": 2})
        self.assertEqual(len(stats["rounds"]), 2)

    def test_legacy_profiles_and_test_mode_are_not_backfilled(self):
        legacy = profile_manager._default_profile(2)
        del legacy["play_time_stats"]
        profile_manager.save_profile(legacy)
        profile_manager.record_player_time(2, 1, "old", 10)
        profile_manager.record_player_time(1, 1, "test", 10, test_mode=True)
        self.assertIsNone(profile_manager.load_profile(2)["play_time_stats"])
        self.assertEqual(profile_manager.load_profile(1)["play_time_stats"]["total_seconds"], 0)

    def test_round_duration_accepts_zero_and_negative_as_zero(self):
        stats = empty_stats()
        record(stats, 1, "zero", 0)
        record(stats, 1, "negative", -4)
        self.assertEqual(stats["total_seconds"], 0)
        self.assertEqual(stats["levels"]["1"]["rounds"], 2)


if __name__ == "__main__":
    unittest.main()
