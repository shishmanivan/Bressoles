import io
import unittest
from unittest import mock

import game_data


class LevelGoalLoadingTests(unittest.TestCase):
    def setUp(self):
        for level in (4, 5):
            patch = mock.patch.object(game_data, f"_goals_level{level}_cache", None)
            patch.start()
            self.addCleanup(patch.stop)

    def test_supported_columns_and_stage_fallback_keep_their_meaning(self):
        table = ";1;2;B1_1;B 2 - 1;Boss Round1;BossRound2\n e ;10;20;0;31;100;200\n"
        with (
            mock.patch.object(game_data.os.path, "exists", return_value=True),
            mock.patch("builtins.open", side_effect=lambda *args, **kwargs: io.StringIO(table)),
        ):
            for level in (4, 5):
                goal = getattr(game_data, f"get_level{level}_goal")
                with self.subTest(level=level):
                    self.assertEqual(goal(1, " e ", 0), 0)
                    self.assertEqual(goal(1, "E", 1), 31)
                    self.assertEqual(goal(1, "E", 2), 10)
                    self.assertEqual(goal(2, "E", 1), 20)
                    self.assertEqual(goal(None, "E", 1), 200)
                    self.assertEqual(goal(1, "E", 1, True), 200)
                    self.assertIsNone(goal(None, "E", 2))
                    self.assertIsNone(goal(1, "unknown", 0))
                    self.assertIsNone(goal("bad", "E", 0))
                    self.assertEqual(goal(1, "E", "bad"), 0)

    def test_invalid_cells_do_not_discard_other_goals(self):
        table = (
            ";1;2;3;BossRound1;BossRound2;B1_1;B2_1;Bbad_1;Unknown\n"
            "E;bad;20;;bad;200;bad;31;999;888;extra cell\n"
            "M;15;25;35;150;250;16;26;;\n"
            "X;999;999;999;999;999;999;999;;\n"
        )
        with (
            mock.patch.object(game_data.os.path, "exists", return_value=True),
            mock.patch("builtins.open", side_effect=lambda *args, **kwargs: io.StringIO(table)),
        ):
            for level in (4, 5):
                with self.subTest(level=level):
                    goals = getattr(game_data, f"load_goals_level{level}")()
                    self.assertEqual(goals["E"], {2: 20, ("boss", 2): 200, (2, 1): 31})
                    self.assertEqual(goals["M"][1], 15)
                    self.assertEqual(goals["H"], {})
                    self.assertNotIn("X", goals)

    def test_levels_keep_separate_caches_and_read_each_file_only_once(self):
        def open_table(path, *args, **kwargs):
            return io.StringIO(";1\nE;40\n" if path == "GoalsLevel4.csv" else ";1\nE;50\n")

        with (
            mock.patch.object(game_data.os.path, "exists", return_value=True),
            mock.patch("builtins.open", side_effect=open_table) as source,
        ):
            fourth = game_data.load_goals_level4()
            fifth = game_data.load_goals_level5()
            self.assertEqual(fourth["E"][1], 40)
            self.assertEqual(fifth["E"][1], 50)
            self.assertIs(game_data.load_goals_level4(), fourth)
            self.assertIs(game_data.load_goals_level5(), fifth)
            self.assertIsNot(fourth, fifth)
            self.assertEqual([call.args[0] for call in source.call_args_list], ["GoalsLevel4.csv", "GoalsLevel5.csv"])

    def test_missing_files_return_and_cache_empty_tables(self):
        with (
            mock.patch.object(game_data.os.path, "exists", return_value=False) as exists,
            mock.patch("builtins.open") as source,
            mock.patch("builtins.print") as warning,
        ):
            for level in (4, 5):
                loader = getattr(game_data, f"load_goals_level{level}")
                first = loader()
                self.assertEqual(first, {"E": {}, "M": {}, "H": {}})
                self.assertIs(loader(), first)
                warning.assert_called_with(f"WARNING: GoalsLevel{level}.csv not found: GoalsLevel{level}.csv")
            self.assertEqual(exists.call_count, 2)
            source.assert_not_called()

    def test_read_errors_keep_filename_in_diagnostic_and_cache_empty_result(self):
        with (
            mock.patch.object(game_data.os.path, "exists", return_value=True),
            mock.patch("builtins.open", side_effect=OSError("unreadable")) as source,
            mock.patch("builtins.print") as warning,
        ):
            for level in (4, 5):
                loader = getattr(game_data, f"load_goals_level{level}")
                first = loader()
                self.assertEqual(first, {"E": {}, "M": {}, "H": {}})
                self.assertIs(loader(), first)
                warning.assert_called_with(f"ERROR loading GoalsLevel{level}.csv: unreadable")
            self.assertEqual(source.call_count, 2)


if __name__ == "__main__":
    unittest.main()
