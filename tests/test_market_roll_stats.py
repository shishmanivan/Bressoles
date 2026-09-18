import csv
import os
import random
import tempfile
import unittest
from unittest import mock

from gameplay_price_helpers import build_stock_price_animation_queue
from market_roll_stats import MarketRollStats


class MarketRollStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = os.path.join(self.temp.name, "rolls.csv")
        self.summary = os.path.join(self.temp.name, "summary.csv")
        self.stats = MarketRollStats(self.journal, self.summary)

    @staticmethod
    def _rolls(values=(0.10, 0.25, 0.90), **kwargs):
        rolls = []
        with mock.patch("gameplay_price_helpers.random.random", side_effect=values):
            queue = build_stock_price_animation_queue(2, 4, 6, random_rolls=rolls, **kwargs)
        return queue, rolls

    @staticmethod
    def _read(path):
        with open(path, encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source, delimiter=";"))

    def test_records_sampled_result_and_complete_probability_snapshot(self):
        _, rolls = self._rolls((0.1, 0.05, 0.9))
        self.stats.record(rolls, profile_slot=2, level=3, round_num=1, day=4)
        rows = self._read(self.journal)
        self.assertEqual([(r["Акция"], r["Результат"], float(r["ВероятностьРезультата%"])) for r in rows],
                         [("A", "Флет", 15), ("B", "Падение", 10), ("C", "Рост", 50)])
        self.assertEqual(len({r["БросокID"] for r in rows}), 1)
        self.assertTrue(all(r["Профиль"] == "2" and r["День"] == "4" for r in rows))
        self.assertEqual(float(rows[2]["ВероятностьПадения%"]), 30)
        self.assertEqual(float(rows[2]["СлучайноеЧисло0до100"]), 90)

    def test_forced_c_does_not_remove_random_a_and_b(self):
        queue, rolls = self._rolls((0.1, 0.9), forced_rise_markets={2})
        self.assertEqual([r["market"] for r in rolls], [0, 1])
        self.assertEqual(queue[2]["type"], "rise")

    def test_forced_fall_flat_and_guaranteed_probability_are_excluded(self):
        cases = [
            ({"forced_fall_markets": {1}}, [0, 2]),
            ({"force_flat": True}, []),
            ({"market_cards": {0: {}, 1: {}, 2: {}}, "force_flat_markets": {1}}, [0, 2]),
            ({"market_cards": {0: {0: 2}}, "probability_card_bonus": 100}, [1, 2]),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                _, rolls = self._rolls(**kwargs)
                self.assertEqual([r["market"] for r in rolls], expected)

    def test_blue_chips_cancelled_forcing_records_actual_random_roll(self):
        _, rolls = self._rolls(forced_fall_markets={2}, prevent_fall_markets={2})
        self.assertEqual(rolls[2]["probabilities"], {"fall": 0, "flat": 35, "rise": 65})

    def test_probability_modifiers_are_captured_at_sampling_time(self):
        cards = {0: {}, 1: {}, 2: {0: 1}}
        _, rolls = self._rolls(market_cards=cards, probability_card_bonus=5)
        cards[2].clear()
        self.assertEqual(rolls[2]["probabilities"], {"fall": 25, "flat": 15, "rise": 60})

    def test_instrumentation_does_not_change_rng_or_animation_contract(self):
        rng = random.Random(9831)
        with mock.patch("gameplay_price_helpers.random.random", side_effect=rng.random):
            state = rng.getstate()
            plain = build_stock_price_animation_queue(2, 4, 6)
            end_state = rng.getstate()
            rng.setstate(state)
            audited = build_stock_price_animation_queue(2, 4, 6, random_rolls=[])
        self.assertEqual(plain, audited)
        self.assertEqual(end_state, rng.getstate())

    def test_summary_uses_all_trials_and_weights_changing_probabilities(self):
        _, first = self._rolls((0.9, 0.9, 0.9))
        _, second = self._rolls((0.9, 0.9, 0.1), market_cards={2: {0: 1}}, probability_card_bonus=5)
        self.stats.record(first, profile_slot=1)
        # A new recorder models switching profiles / restarting the application.
        MarketRollStats(self.journal, self.summary).record(second, profile_slot=2)
        rows = self._read(self.summary)
        total = next(r for r in rows if r["Выборка"] == "Общая" and r["Акция"] == "C"
                     and r["Результат"] == "Рост" and r["ВероятностьГруппы%"] == "Все")
        self.assertEqual(total["СлучайныхБросков"], "2")
        self.assertEqual(total["Фактически"], "1")
        self.assertEqual(float(total["Ожидалось"]), 1.1)
        self.assertEqual(float(total["Ожидалось%"]), 55)
        self.assertEqual(float(total["РазницаПП"]), -5)
        profiles = [r for r in rows if r["Выборка"] == "Профиль" and r["Акция"] == "C"
                    and r["Результат"] == "Рост" and r["ВероятностьГруппы%"] == "Все"]
        self.assertEqual([(r["Профиль"], r["СлучайныхБросков"], r["Фактически"]) for r in profiles],
                         [("1", "1", "1"), ("2", "1", "0")])
        # Misses at a given probability must still appear in that probability group.
        miss = next(r for r in rows if r["Выборка"] == "Общая" and r["Акция"] == "C"
                    and r["Результат"] == "Рост" and r["ВероятностьГруппы%"] == "60.0")
        self.assertEqual((miss["СлучайныхБросков"], miss["Фактически"]), ("1", "0"))
        # Original recorder also detects writes by a different round's recorder.
        self.stats.record(first, profile_slot=1)
        self.assertEqual(len(self._read(self.journal)), 9)

    def test_empty_batch_writes_nothing(self):
        self.stats.record([], profile_slot=1)
        self.assertFalse(os.path.exists(self.journal))
        self.assertFalse(os.path.exists(self.summary))

    def test_locked_report_preserves_journal_and_rebuild_does_not_duplicate_rolls(self):
        _, rolls = self._rolls()
        with mock.patch("market_roll_stats.write_semicolon_csv_atomically", side_effect=PermissionError("locked")):
            with self.assertLogs("market_roll_stats", level="ERROR"):
                self.stats.record(rolls, profile_slot=1)
        self.assertEqual(len(self._read(self.journal)), 3)
        MarketRollStats(self.journal, self.summary).rebuild_summary()
        self.assertEqual(len(self._read(self.journal)), 3)
        self.assertTrue(self._read(self.summary))

    def test_gameplay_records_before_extra_insider_movements(self):
        from gameplay_page import GameplayPage

        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = []
        page.active_black_cards = []
        page.active_gold_cards = [405, 405]
        page.active_lifecycle_card_order = []
        page.profile_slot, page.level_number, page.round_num, page.Day = 3, 1, 2, 1
        page.test_mode = False
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page.market_roll_stats = self.stats
        with mock.patch("gameplay_price_helpers.random.random", return_value=0.9):
            movements = page.update_stock_prices()
        self.assertEqual(len([m for m in movements if m["market"] == 2]), 2)
        rows = self._read(self.journal)
        self.assertEqual([r["Акция"] for r in rows], ["A", "B"])
        self.assertTrue(all(r["Профиль"] == "3" for r in rows))


if __name__ == "__main__":
    unittest.main()
