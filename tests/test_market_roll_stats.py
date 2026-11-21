import csv
from collections import Counter
import multiprocessing
import os
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest import mock

from gameplay_price_helpers import build_stock_price_animation_queue
from market_roll_stats import MarketRollStats


def _record_in_game_window(journal, summary, slot, start):
    if not start.wait(15):
        raise RuntimeError("other game did not start")
    stats = MarketRollStats(journal, summary)
    rolls = [{"market": i, "outcome": "rise", "probabilities": {"rise": 50, "flat": 20, "fall": 30},
              "random_value": 90} for i in range(3)]
    for day in range(8):
        stats.record(rolls, profile_slot=slot, day=day)
    stats.summary_task.result(timeout=15)


class MarketRollStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = os.path.join(self.temp.name, "rolls.csv")
        self.summary = os.path.join(self.temp.name, "summary.csv")
        self.stats = MarketRollStats(self.journal, self.summary)
        self.addCleanup(self.wait_for_summary)

    def wait_for_summary(self):
        if self.stats.summary_task is not None:
            self.stats.summary_task.result(timeout=10)

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
        queue, rolls = self._rolls((0.1, 0.9, 0.5), forced_rise_markets={2})
        self.assertEqual([r["market"] for r in rolls], [0, 1, 2])
        self.assertEqual(queue[2]["type"], "rise")

    def test_forced_fall_flat_and_guaranteed_probability_are_excluded(self):
        cases = [
            ({"forced_fall_markets": {1}}, [0, 1, 2]),
            ({"force_flat": True}, []),
            ({"market_cards": {0: {}, 1: {}, 2: {}}, "force_flat_markets": {1}}, [0, 1, 2]),
            ({"market_cards": {0: {0: 2}}, "probability_card_bonus": 100}, [0, 1, 2]),
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
        other = MarketRollStats(self.journal, self.summary)
        other.record(second, profile_slot=2)
        other.summary_task.result(timeout=10)
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

    def test_two_game_windows_publish_all_batches_once(self):
        context = multiprocessing.get_context("spawn")
        start = context.Event()
        processes = []
        try:
            for slot in (1, 2):
                process = context.Process(target=_record_in_game_window,
                                          args=(self.journal, self.summary, slot, start))
                process.start()
                processes.append(process)
            start.set()
            for process in processes:
                process.join(30)
                self.assertEqual(process.exitcode, 0)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                process.join()
                process.close()
        rows = self._read(self.journal)
        self.assertEqual(len(rows), 48)
        batches = Counter(row["БросокID"] for row in rows)
        self.assertEqual(len(batches), 16)
        self.assertEqual(set(batches.values()), {3})
        self.assertEqual(len({(r["Профиль"], r["День"], r["Акция"]) for r in rows}), 48)
        concurrent_report = Path(self.summary).read_bytes()
        self.stats.rebuild_summary()
        self.assertEqual(concurrent_report, Path(self.summary).read_bytes())

    def test_locked_report_preserves_journal_and_rebuild_does_not_duplicate_rolls(self):
        _, rolls = self._rolls()
        replace = os.replace
        def deny_summary(source, target):
            if os.fspath(target) == self.summary:
                raise PermissionError("locked by reader")
            replace(source, target)
        with mock.patch("disk_storage.os.replace", side_effect=deny_summary), mock.patch(
            "disk_storage.error_handler", side_effect=AssertionError("modal dialog")
        ) as handler, self.assertLogs("market_roll_stats", level="ERROR"):
            self.stats.record(rolls, profile_slot=1)
            self.wait_for_summary()
        handler.assert_not_called()
        self.assertEqual(len(self._read(self.journal)), 3)
        self.stats.record(rolls, profile_slot=1)
        self.wait_for_summary()
        self.assertEqual(len(self._read(self.journal)), 6)
        report = Path(self.summary).read_bytes()
        MarketRollStats(self.journal, self.summary).rebuild_summary()
        self.assertEqual(Path(self.summary).read_bytes(), report)

    def test_slow_summary_leaves_journal_available_to_next_round(self):
        _, rolls = self._rolls()
        started, release = threading.Event(), threading.Event()
        def slow_write():
            started.set()
            if not release.wait(5):
                raise AssertionError("game thread waited for the report")
        with mock.patch.object(self.stats._summary, "_write_report", side_effect=slow_write):
            try:
                self.stats.record(rolls)
                self.assertTrue(started.wait(5))
                other = MarketRollStats(self.journal, self.summary)
                other.record(rolls)
                self.assertEqual(len(self._read(self.journal)), 6)
            finally:
                release.set()
            other.summary_task.result(timeout=10)

    def test_next_round_only_aggregates_appended_rows(self):
        _, rolls = self._rolls()
        self.stats.record(rolls)
        self.wait_for_summary()
        prefix = Path(self.journal).read_bytes()
        other = MarketRollStats(self.journal, self.summary)
        with mock.patch.object(other._summary, "_read_groups", wraps=other._summary._read_groups) as read:
            other.record(rolls)
            other.summary_task.result(timeout=10)
        self.assertTrue(Path(self.journal).read_bytes().startswith(prefix))
        read.assert_called_once_with(len(prefix), os.path.getsize(self.journal))

    def test_restart_completes_interrupted_batch_once(self):
        _, rolls = self._rolls()
        journal = Path(self.journal)
        self.stats.record(rolls)
        self.wait_for_summary()
        original = journal.read_bytes()
        import market_roll_stats
        finish = market_roll_stats._finish_pending
        for tail in (0, 7, None):
            with self.subTest(tail=tail):
                journal.write_bytes(original)
                def crash(path, pending):
                    if not pending.exists():
                        return finish(path, pending)
                    with path.open("ab") as output:
                        output.write(pending.read_bytes()[8:][:tail])
                    raise SystemExit("interrupted before pending batch was cleared")
                with mock.patch.object(market_roll_stats, "_finish_pending", side_effect=crash):
                    with self.assertRaises(SystemExit):
                        self.stats.record(rolls)
                restarted = MarketRollStats(self.journal, self.summary)
                restarted.rebuild_summary()
                restarted.rebuild_summary()
                rows = self._read(self.journal)
                self.assertEqual([row["Акция"] for row in rows], list("ABCABC"))
                self.assertEqual(len({row["БросокID"] for row in rows}), 2)

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
        self.assertEqual([r["Акция"] for r in rows], ["A", "B", "C"])
        self.assertTrue(all(r["Профиль"] == "3" for r in rows))


if __name__ == "__main__":
    unittest.main()
