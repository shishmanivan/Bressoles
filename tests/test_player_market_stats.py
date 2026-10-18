import json
import os
import tempfile
import unittest
from unittest import mock

import profile_manager
from player_market_stats import summarize


class PlayerMarketStatsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = mock.patch.object(profile_manager, "PROFILES_DIR", directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        profile_manager.save_profile(profile_manager._default_profile(1))

    @staticmethod
    def roll(market=0, outcome="rise", rise=80):
        return {"market": market, "outcome": outcome,
                "probabilities": {"rise": rise, "fall": 100 - rise, "flat": 0}}

    def stats(self, slot=1):
        return profile_manager.load_profile(slot)["market_roll_stats"]

    def test_two_scopes_weight_probabilities_and_survive_reload(self):
        profile_manager.record_player_market_rolls(1, [self.roll(), self.roll(1)], (1, 0, 0))
        profile_manager.record_player_market_rolls(1, [self.roll(outcome="fall", rise=20)], (50, 0, 0))
        profile_manager.record_player_market_rolls(1, [self.roll(rise=50)], (0, 0, 0))
        stats = self.stats()
        overall = summarize(stats)["A"]
        held = summarize(stats, "invested")["A"]
        self.assertEqual(overall["rolls"], 3)
        self.assertEqual(held["rolls"], 2)
        self.assertEqual(overall["outcomes"]["rise"]["actual"], 2)
        self.assertAlmostEqual(overall["outcomes"]["rise"]["expected_percent"], 50)
        self.assertAlmostEqual(held["outcomes"]["rise"]["actual_percent"], 50)
        self.assertAlmostEqual(held["outcomes"]["rise"]["expected_percent"], 50)
        self.assertEqual(stats["all"]["B"]["rolls"], 1)
        self.assertEqual(stats["invested"]["B"]["rolls"], 0)
        self.assertIsNone(summarize(stats)["C"]["outcomes"]["rise"]["actual_percent"])

    def test_old_profiles_do_not_opt_in_or_import_technical_history(self):
        old = profile_manager._default_profile(2)
        del old["market_roll_stats"]
        profile_manager.save_profile(old)
        profile_manager.record_player_market_rolls(2, [self.roll()], (1, 1, 1))
        self.assertIsNone(self.stats(2))
        with open(profile_manager.get_profile_path(2), encoding="utf-8") as source:
            self.assertNotIn("market_roll_stats", json.load(source))

    def test_test_mode_empty_batch_and_missing_profile_are_ignored(self):
        profile_manager.record_player_market_rolls(1, [self.roll()], (1, 1, 1), test_mode=True)
        profile_manager.record_player_market_rolls(1, [], (1, 1, 1))
        profile_manager.record_player_market_rolls(None, [self.roll()], (1, 1, 1))
        profile_manager.record_player_market_rolls(3, [self.roll()], (1, 1, 1))
        self.assertEqual(self.stats()["all"]["A"]["rolls"], 0)
        self.assertFalse(os.path.exists(profile_manager.get_profile_path(3)))

    def test_progress_save_and_run_end_preserve_lifetime_stats(self):
        profile_manager.record_player_market_rolls(1, [self.roll(2, "flat")], (0, 0, 1))
        before = self.stats()
        profile_manager.save_progress_from_game_state(1)
        profile_manager.save_active_game(1, {"level_number": 1}, {"Day": 1})
        profile_manager.clear_active_game(1)
        self.assertEqual(self.stats(), before)

    def test_profiles_and_reused_slots_have_separate_counters(self):
        profile_manager.record_player_market_rolls(1, [self.roll()], (1, 0, 0))
        profile_manager.save_profile(profile_manager._default_profile(2))
        self.assertEqual(self.stats(2)["all"]["A"]["rolls"], 0)
        with mock.patch.object(profile_manager, "get_selected_slot", return_value=None):
            profile_manager.delete_profile(1)
        profile_manager.save_profile(profile_manager._default_profile(1))
        self.assertEqual(self.stats()["all"]["A"]["rolls"], 0)

    def test_gameplay_records_holdings_and_actual_sampler_results(self):
        from gameplay_page import GameplayPage
        from market_roll_stats import MarketRollStats

        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = []
        page.active_black_cards = []
        page.active_gold_cards = []
        page.active_lifecycle_card_order = []
        page.profile_slot, page.level_number, page.round_num, page.Day = 1, 1, 1, 1
        page.test_mode = False
        page.Aquantity, page.Bquantity, page.Cquantity = 0, 2, 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page.market_roll_stats = mock.Mock(spec=MarketRollStats)
        with mock.patch("gameplay_price_helpers.random.random", return_value=0.9):
            page.update_stock_prices()
        stats = self.stats()
        self.assertEqual([stats["all"][s]["rolls"] for s in "ABC"], [1, 1, 1])
        self.assertEqual([stats["invested"][s]["rolls"] for s in "ABC"], [0, 1, 0])
        self.assertEqual(stats["invested"]["B"]["actual"]["rise"], 1)


if __name__ == "__main__":
    unittest.main()
