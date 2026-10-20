import tempfile
import unittest
from unittest.mock import patch

import profile_manager
from gameplay_other_stats import OtherStatsMixin


class LifecycleCardStatsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(profile_manager, "PROFILES_DIR", directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        profile_manager.save_profile(profile_manager._default_profile(1))

    def counts(self, slot=1):
        return profile_manager.load_profile(slot)["lifecycle_card_stats"]["counts"]

    def test_each_copy_counts_once_per_round_even_after_reloading(self):
        cards = [201, 201, 407, 301, 11, 111]
        profile_manager.record_player_lifecycle_cards(1, "first", cards)
        profile_manager.record_player_lifecycle_cards(1, "first", cards)
        self.assertEqual(self.counts(), {"201": 2, "407": 1, "301": 1})
        profile_manager.record_player_lifecycle_cards(1, "second", [201, 407, 301])
        self.assertEqual(self.counts(), {"201": 3, "407": 2, "301": 2})
        profile_manager.record_player_lifecycle_cards(1, "first", cards)
        self.assertEqual(self.counts()["201"], 3)

    def test_legacy_profiles_test_mode_and_missing_slots_do_not_record(self):
        legacy = profile_manager._default_profile(2)
        del legacy["lifecycle_card_stats"]
        profile_manager.save_profile(legacy)
        profile_manager.record_player_lifecycle_cards(2, "round", [201])
        self.assertIsNone(profile_manager.load_profile(2)["lifecycle_card_stats"])
        profile_manager.record_player_lifecycle_cards(1, "round", [201], test_mode=True)
        profile_manager.record_player_lifecycle_cards(None, "round", [201])
        profile_manager.record_player_lifecycle_cards(3, "round", [201])
        self.assertEqual(self.counts(), {})

    def test_profile_isolation_and_progress_save(self):
        profile_manager.save_profile(profile_manager._default_profile(2))
        profile_manager.record_player_lifecycle_cards(1, "round", [305, 414])
        profile_manager.save_progress_from_game_state(1)
        profile_manager.save_active_game(1, {}, {})
        profile_manager.clear_active_game(1)
        self.assertEqual(self.counts(), {"305": 1, "414": 1})
        self.assertEqual(self.counts(2), {})

    def test_gameplay_commit_uses_only_active_cards_and_survives_saved_replay(self):
        page = OtherStatsMixin()
        page.profile_slot, page.test_mode, page.level_number = 1, False, 1
        page._init_other_stats()
        page.active_silver_cards = [201, 201]
        page.active_black_cards = [301]
        page.active_gold_cards = [407]
        snapshot = {"other_stats": page._serialize_other_stats()}
        self.assertEqual(self.counts(), {})
        page._commit_lifecycle_card_stats()
        page._commit_lifecycle_card_stats()
        self.assertEqual(self.counts(), {"201": 2, "301": 1, "407": 1})
        page._restore_other_stats(snapshot)
        page._commit_lifecycle_card_stats()
        self.assertEqual(self.counts(), {"201": 2, "301": 1, "407": 1})


if __name__ == "__main__":
    unittest.main()
