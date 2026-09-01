import os
import csv
import tempfile
import unittest
from unittest import mock

import csv_storage
import game_stats
import shop_card_stats


class StatsContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.game_stats_path = os.path.join(self.temp_dir.name, "game.csv")
        self.shop_stats_path = os.path.join(self.temp_dir.name, "shop.csv")
        self.original_game_stats_path = game_stats.STATS_FILE
        self.original_level6_experiment_stats_path = game_stats.LEVEL6_EXPERIMENT_STATS_FILE
        self.original_shop_stats_path = shop_card_stats.STATS_FILE
        game_stats.set_stats_file(self.game_stats_path)
        game_stats.set_level6_experiment_stats_file(None)
        shop_card_stats.set_shop_card_stats_file(self.shop_stats_path)

    def tearDown(self):
        game_stats.STATS_FILE = self.original_game_stats_path
        game_stats.LEVEL6_EXPERIMENT_STATS_FILE = self.original_level6_experiment_stats_path
        shop_card_stats.STATS_FILE = self.original_shop_stats_path
        self.temp_dir.cleanup()

    def test_every_configured_boss_has_a_real_name(self):
        self.assertEqual(
            [game_stats.get_boss_name(number) for number in range(1, 11)],
            [
                "Джеймс Уатт",
                "Адам Смит",
                "Роберт Фултон",
                "Николя Аппер",
                "Сэмюэль Слейтер",
                "Ричард Аркрайт",
                "Адольф Кольбе",
                "Фридрих Лист",
                "Жак Лаффит",
                "Роберт Стефенсон",
            ],
        )

    def test_round_and_level_run_counters_remain_separate(self):
        game_stats.update_level_run_started(4)
        game_stats.update_game_stats(4, 10, "Босс", True, "Boss")
        game_stats.update_level_boss_position_stats(4, 3, True)
        game_stats.update_level_run_result(4, True)

        rows = game_stats._read_rows()
        run_row = next(row for row in rows if row["Раунд"] == game_stats.LEVEL_RUN_ROUND_LABEL)
        boss_row = next(row for row in rows if row["Раунд"] == "Босс")
        position_row = next(row for row in rows if row["Раунд"] == game_stats.LEVEL_BOSS_ROUND_LABEL)

        self.assertEqual((run_row["Сыграно"], run_row["Победы"], run_row["Поражения"]), ("1", "1", "0"))
        self.assertEqual((boss_row["Босс"], boss_row["Победы"]), ("Роберт Стефенсон", "1"))
        self.assertEqual((position_row["БоссНомер"], position_row["Победы"]), ("3", "1"))

    def test_round_money_stats_are_aggregated(self):
        game_stats.update_game_stats(4, 10, "Раунд 1", True, "M", earned_money=37)
        game_stats.update_game_stats(4, 10, "Раунд 1", False, "M", earned_money=13)

        row = game_stats._read_rows()[0]

        self.assertEqual(row["ДеньгиВсего"], "50")
        self.assertEqual(row["ДеньгиСреднее"], "25")
        self.assertEqual(row["ДеньгиМаксимум"], "37")
        self.assertEqual(row["ДеньгиПоследние"], "13")

    def test_level8_sequential_round_numbers_do_not_shift_for_fulton(self):
        self.assertEqual(
            [
                game_stats.build_sequential_round_number(8, round_num, 1, boss_number=3)
                for round_num in range(1, 5)
            ],
            ["1", "2", "3", "3.5"],
        )
        self.assertEqual(
            game_stats.build_sequential_round_number(8, boss_position=1, is_boss_fight=True),
            "4",
        )
        self.assertEqual(
            [
                game_stats.build_sequential_round_number(8, round_num, 2, boss_number=3)
                for round_num in range(1, 5)
            ],
            ["5", "6", "7", "7.5"],
        )
        self.assertEqual(
            game_stats.build_sequential_round_number(8, boss_position=2, is_boss_fight=True),
            "8",
        )
        self.assertEqual(game_stats.build_sequential_round_number(5, 1, 1), "")

    def test_level8_round_stats_are_split_by_sequential_round_number(self):
        game_stats.update_game_stats(
            8, 3, "Раунд 2", True, "M", earned_money=400, sequential_round_number="2"
        )
        game_stats.update_game_stats(
            8, 3, "Раунд 2", False, "M", earned_money=500, sequential_round_number="6"
        )

        rows = game_stats._read_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [(row["ПорядковыйРаунд"], row["Победы"], row["Поражения"]) for row in rows],
            [("2", "1", "0"), ("6", "0", "1")],
        )

    def test_level8_loss_stage_uses_sequential_round_number(self):
        game_stats.update_level_run_loss_stage_stats(
            8,
            "Раунд 3",
            3,
            boss_position=2,
            boss_number=5,
        )
        game_stats.update_level_run_loss_stage_stats(8, "Босс уровня 2", 2)

        rows = game_stats._read_rows()
        self.assertEqual(
            sorted(row["ПорядковыйРаунд"] for row in rows),
            ["7", "8"],
        )

    def test_level6_experiment_log_is_parallel_and_starts_without_history(self):
        experiment_path = os.path.join(self.temp_dir.name, "level6_experiment.csv")
        game_stats.update_game_stats(8, 3, "Раунд 1", True, "M", earned_money=999)
        game_stats.set_level6_experiment_stats_file(experiment_path)

        game_stats.update_game_stats(5, 3, "Раунд 1", True, "M", earned_money=55)
        game_stats.update_game_stats(8, 3, "Раунд 2", False, "H", earned_money=321)
        game_stats.update_level_run_started(8)

        primary_rows = game_stats._read_rows(self.game_stats_path)
        experiment_rows = game_stats._read_rows(experiment_path)

        self.assertEqual(len(primary_rows), 4)
        self.assertTrue(any(row["ДеньгиВсего"] == "999" for row in primary_rows))
        self.assertFalse(any(row["ДеньгиВсего"] == "999" for row in experiment_rows))
        self.assertTrue(all(row["Уровень"] == "8" for row in experiment_rows))
        round_row = next(row for row in experiment_rows if row["Раунд"] == "Раунд 2")
        self.assertEqual((round_row["Сыграно"], round_row["Поражения"], round_row["ДеньгиВсего"]), ("1", "1", "321"))

    def test_legacy_generic_boss_name_is_normalized_without_changing_counts(self):
        legacy_row = game_stats._new_stats_row("4", "10", "Босс 10", "Раунд 2", "M")
        legacy_row.update({"Сыграно": "7", "Победы": "5", "Поражения": "2"})
        game_stats._write_rows([legacy_row])

        restored = game_stats._read_rows()[0]

        self.assertEqual(restored["Босс"], "Роберт Стефенсон")
        self.assertEqual((restored["Сыграно"], restored["Победы"], restored["Поражения"]), ("7", "5", "2"))

    def test_legacy_stats_file_is_migrated_with_blank_sequential_round(self):
        legacy_fields = [field for field in game_stats.FIELDNAMES if field != "ПорядковыйРаунд"]
        legacy_row = game_stats._new_stats_row("6", "3", "Роберт Фултон", "Раунд 2", "M")
        legacy_row.update({"Сыграно": "2", "Победы": "1", "Поражения": "1"})
        with open(self.game_stats_path, "w", encoding="utf-8-sig", newline="") as stats_file:
            writer = csv.DictWriter(stats_file, fieldnames=legacy_fields, delimiter=";", extrasaction="ignore")
            writer.writeheader()
            writer.writerow(legacy_row)

        game_stats.ensure_stats_file(self.game_stats_path)

        with open(self.game_stats_path, "r", encoding="utf-8-sig", newline="") as stats_file:
            self.assertEqual(next(csv.reader(stats_file, delimiter=";")), game_stats.FIELDNAMES)
        restored = game_stats._read_rows(self.game_stats_path)[0]
        self.assertEqual(restored["ПорядковыйРаунд"], "")
        self.assertEqual((restored["Сыграно"], restored["Победы"], restored["Поражения"]), ("2", "1", "1"))

    def test_shop_offer_statistics_use_total_card_slots(self):
        shop_card_stats.record_shop_card_offers(
            4,
            [
                {"kind": "card", "card_id": 117},
                {"kind": "card", "card_id": 401},
                {"kind": "special", "special_id": "bank"},
            ],
        )
        shop_card_stats.record_shop_card_offers(4, [{"kind": "card", "card_id": 117}])

        rows = shop_card_stats._read_rows()
        by_card = {int(row["КартаНомер"]): row for row in rows}
        self.assertEqual(by_card[117]["Выпадений"], "2")
        self.assertEqual(by_card[401]["Выпадений"], "1")
        self.assertEqual(by_card[117]["ВсегоКарточныхСлотов"], "3")
        self.assertEqual(by_card[117]["ПроцентОтСлотов"], "66.67")
        self.assertEqual(by_card[401]["ПроцентОтСлотов"], "33.33")

    def test_failed_atomic_stats_replace_preserves_previous_file(self):
        game_stats.update_game_stats(1, 1, "Раунд 1", True, "E")
        with open(self.game_stats_path, "rb") as stats_file:
            original = stats_file.read()

        with mock.patch.object(csv_storage.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                game_stats.update_game_stats(1, 1, "Раунд 1", False, "E")

        with open(self.game_stats_path, "rb") as stats_file:
            self.assertEqual(stats_file.read(), original)
        self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(self.temp_dir.name)))


if __name__ == "__main__":
    unittest.main()
