import json
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import game_state
import profile_manager
from gameplay_other_stats import OtherStatsMixin
from player_other_stats import empty_stats, record, average


class OtherStatsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(profile_manager, "PROFILES_DIR", directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(game_state, "boss_progress", {})
        patcher.start()
        self.addCleanup(patcher.stop)
        profile_manager.save_profile(profile_manager._default_profile(1))

    def page(self):
        page = OtherStatsMixin()
        page.profile_slot, page.test_mode = 1, False
        page.level_number, page.round_num, page.Day = 3, 1, 1
        page.is_boss_fight = False
        page.Money = 100
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page._get_active_boss_number = Mock(return_value=None)
        page._init_other_stats()
        page.market_cards = {0: {0: 11, 1: 12}, 1: {0: 201}, 2: {}}
        page.market_cards_locked = {0: {1: True}, 1: {}, 2: {}}
        page.side_cards_top = [111, 401, 301, None]
        page.side_cards_locked_top = {}
        return page

    def test_committed_ordinary_cards_only_once_per_end(self):
        page = self.page()
        self.assertEqual(page.other_stats_run["cards"], 0)
        page._commit_other_stats_cards()
        page._commit_other_stats_cards()
        self.assertEqual(page.other_stats_run["cards"], 2)
        page.market_cards_locked[0][0] = True
        page.side_cards_locked_top[0] = True
        page.Day = 2
        page._commit_other_stats_cards()
        self.assertEqual(page.other_stats_run["cards"], 2)
        self.assertEqual(profile_manager.load_profile(1)["other_stats"]["cards"], 2)

    def test_best_average_defeat_and_duplicate_completion(self):
        stats = empty_stats()
        record(stats, "first", 3, earned=100, label={"round": 1})
        record(stats, "first", 3, earned=100, label={"round": 1})
        record(stats, "second", 2, earned=-20, label={"round": 2})
        self.assertEqual(stats["cards"], 5)
        self.assertEqual(stats["rounds"], 2)
        self.assertEqual(average(stats), 40)
        self.assertEqual(stats["best"]["label"]["round"], 1)
        self.assertIsNone(average(empty_stats()))

    def test_save_restore_and_replayed_checkpoint_do_not_duplicate_lifetime(self):
        page = self.page()
        page._commit_other_stats_cards()
        snapshot = json.loads(json.dumps({"other_stats": page._serialize_other_stats()}))
        page._finish_other_stats()
        page._finish_other_stats()
        restored = self.page()
        restored._restore_other_stats(snapshot)
        restored._commit_other_stats_cards()
        restored._finish_other_stats()
        stats = profile_manager.load_profile(1)["other_stats"]
        self.assertEqual((stats["cards"], stats["rounds"], stats["earned"]), (2, 1, 100))

    def test_new_run_resets_run_summary_but_keeps_profile(self):
        page = self.page()
        page._commit_other_stats_cards()
        page._finish_other_stats()
        serialized = profile_manager._serialize_boss_progress(game_state.boss_progress)
        game_state.boss_progress = profile_manager._restore_boss_progress(json.loads(json.dumps(serialized)))
        next_round = self.page()
        self.assertEqual(next_round.other_stats_run["earned"], 100)
        game_state.boss_progress[3] = game_state.new_boss_progress_state()
        new_run = self.page()
        self.assertEqual(new_run.other_stats_run["rounds"], 0)
        self.assertEqual(new_run.other_stats_lifetime["earned"], 100)

    def test_legacy_profile_and_old_active_save_are_not_backfilled(self):
        profile = profile_manager._default_profile(1)
        del profile["other_stats"]
        profile_manager.save_profile(profile)
        page = self.page()
        page._commit_other_stats_cards()
        page._finish_other_stats()
        self.assertFalse(page.other_stats_enabled)
        self.assertIsNone(profile_manager.load_profile(1)["other_stats"])
        profile_manager.save_profile(profile_manager._default_profile(1))
        page = self.page()
        page._restore_other_stats({})
        self.assertFalse(page.other_stats_enabled)

    def test_test_mode_does_not_record(self):
        page = self.page()
        before = deepcopy(profile_manager.load_profile(1)["other_stats"])
        page.test_mode = True
        page._init_other_stats()
        page._commit_other_stats_cards()
        page._finish_other_stats()
        self.assertEqual(profile_manager.load_profile(1)["other_stats"], before)

    def test_unsold_shares_excluded_but_committed_cards_kept(self):
        page = self.page()
        page._commit_other_stats_cards()
        page.Aquantity = 1
        page._finish_other_stats()
        stats = profile_manager.load_profile(1)["other_stats"]
        self.assertEqual((stats["cards"], stats["rounds"]), (2, 0))
        self.assertIsNone(stats["best"])
        self.assertIsNone(average(stats))

    def test_zero_cash_and_final_rebate_cash_count_in_average(self):
        page = self.page()
        page.Money = 0
        page._finish_other_stats()
        rebate_page = self.page()
        rebate_page.Money = 250
        rebate_page._finish_other_stats()
        stats = profile_manager.load_profile(1)["other_stats"]
        self.assertEqual(stats["rounds"], 2)
        self.assertEqual(average(stats), 125)
        self.assertEqual(stats["best"]["earned"], 250)

    def test_unfinished_round_only_adds_committed_cards(self):
        page = self.page()
        page._commit_other_stats_cards()
        profile_manager.save_active_game(1, {}, {"other_stats": page._serialize_other_stats()})
        stats = profile_manager.load_profile(1)["other_stats"]
        self.assertEqual((stats["cards"], stats["rounds"]), (2, 0))


if __name__ == "__main__":
    unittest.main()
