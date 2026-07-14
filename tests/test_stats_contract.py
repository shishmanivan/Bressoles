import os
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
        self.original_shop_stats_path = shop_card_stats.STATS_FILE
        game_stats.set_stats_file(self.game_stats_path)
        shop_card_stats.set_shop_card_stats_file(self.shop_stats_path)

    def tearDown(self):
        game_stats.STATS_FILE = self.original_game_stats_path
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

    def test_legacy_generic_boss_name_is_normalized_without_changing_counts(self):
        legacy_row = game_stats._new_stats_row("4", "10", "Босс 10", "Раунд 2", "M")
        legacy_row.update({"Сыграно": "7", "Победы": "5", "Поражения": "2"})
        game_stats._write_rows([legacy_row])

        restored = game_stats._read_rows()[0]

        self.assertEqual(restored["Босс"], "Роберт Стефенсон")
        self.assertEqual((restored["Сыграно"], restored["Победы"], restored["Поражения"]), ("7", "5", "2"))

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
