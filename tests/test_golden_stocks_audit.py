import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state


class GoldenStocksRollLogTests(unittest.TestCase):
    def setUp(self):
        self.original_state = (
            game_state.golden_stocks_chance_percent,
            game_state.golden_stocks_triggered,
            list(game_state.gold_cards),
        )
        game_state.golden_stocks_chance_percent = 10
        game_state.golden_stocks_triggered = False
        game_state.gold_cards = []
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp_dir.name) / "GoldenStockChecks.log"
        self.path_patch = mock.patch.object(
            game_state,
            "GOLDEN_STOCKS_AUDIT_PATH",
            self.log_path,
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()
        (
            game_state.golden_stocks_chance_percent,
            game_state.golden_stocks_triggered,
            game_state.gold_cards,
        ) = self.original_state

    def test_each_real_roll_is_written_as_roll_and_current_chance(self):
        with (
            mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
            mock.patch.object(game_state.random, "randint", side_effect=[65, 88, 29]),
        ):
            game_state.resolve_golden_stocks_round([302], record_roll=True)
            game_state.resolve_golden_stocks_round([302], record_roll=True)
            game_state.resolve_golden_stocks_round([302], record_roll=True)

        self.assertEqual(
            self.log_path.read_text(encoding="utf-8").splitlines(),
            ["65 (10)", "88 (12)", "29 (14)"],
        )

    def test_test_calls_do_not_write_anything_by_default(self):
        with (
            mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
            mock.patch.object(game_state.random, "randint", return_value=65),
        ):
            game_state.resolve_golden_stocks_round([302])

        self.assertFalse(self.log_path.exists())

    def test_skipped_checks_do_not_write_anything_even_when_recording_is_enabled(self):
        game_state.resolve_golden_stocks_round([], record_roll=True)
        self.assertFalse(self.log_path.exists())


if __name__ == "__main__":
    unittest.main()
