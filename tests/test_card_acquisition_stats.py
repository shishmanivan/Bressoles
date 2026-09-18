import csv
import os
import tempfile
import unittest
from unittest import mock

import card_acquisition_stats as stats
import game_state
from shop_purchases import buy_card_or_license


class CardAcquisitionStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "cards.csv")
        tracker_patch = mock.patch.object(stats, "_tracker", None)
        tracker_patch.start()
        self.addCleanup(tracker_patch.stop)
        self.configure(2)
        for field, value in (
            ("gold_cards", []), ("shop_deck_cards", []), ("napoleondors", 100),
            ("licensed_card_ids", set(game_state.DEFAULT_LICENSED_CARDS)),
            ("multibagger_bought", False), ("golden_stocks_triggered", False),
            ("golden_stocks_chance_percent", 10), ("golden_stocks_trigger_count", 0),
        ):
            patcher = mock.patch.object(game_state, field, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def configure(self, profile, enabled=True):
        stats.configure_card_acquisition_stats(
            profile, {401: "Медведь", 402: "Форвардная торговля", 117: "Крах"},
            path=self.path, enabled=enabled,
        )

    def counters(self, card, profile="Все"):
        with open(self.path, encoding="utf-8-sig", newline="") as source:
            row = next(row for row in csv.DictReader(source, delimiter=";")
                       if row["КартаНомер"] == str(card) and row["Профиль"] == str(profile))
        return tuple(int(row[field]) for field in stats.COUNTERS.values())

    def test_all_actual_card_offers_count_even_if_unaffordable(self):
        stats.record_card_offers([
            {"kind": "card", "card_id": 401, "cost": 999},
            {"kind": "card", "card_id": 117},
            {"kind": "license", "card_id": 121},
            {"kind": "special", "special_id": "multibagger"},
        ])
        stats.record_card_offers([{"kind": "card", "card_id": 401}])
        self.assertEqual(self.counters(401), (2, 0, 0))
        self.assertEqual(self.counters(117), (1, 0, 0))
        with open(self.path, encoding="utf-8-sig", newline="") as source:
            self.assertEqual(len(list(csv.DictReader(source, delimiter=";"))), 4)

    def test_successful_gold_and_regular_purchases_are_not_bonuses(self):
        for card in (401, 117):
            offer = {"kind": "card", "card_id": card, "cost": 2}
            self.assertTrue(buy_card_or_license(4, offer).purchased)
            self.assertFalse(buy_card_or_license(4, offer).purchased)
            self.assertEqual(self.counters(card), (0, 1, 0))

    def test_failed_purchases_full_inventory_and_licenses_do_not_count(self):
        game_state.napoleondors = 0
        self.assertFalse(buy_card_or_license(4, {"kind": "card", "card_id": 401, "cost": 1}).purchased)
        game_state.gold_cards = [402] * game_state.MAX_GOLD_CARDS
        self.assertFalse(buy_card_or_license(4, {"kind": "card", "card_id": 401, "cost": 0}).purchased)
        buy_card_or_license(4, {"kind": "license", "card_id": 121, "cost": 0})
        self.assertFalse(os.path.exists(self.path))

    def test_free_direct_purchase_still_counts_as_purchase(self):
        self.assertTrue(buy_card_or_license(4, {"kind": "card", "card_id": 401, "cost": 0}).purchased)
        self.assertEqual(self.counters(401), (0, 1, 0))

    def test_bonus_counts_only_successfully_added_gold(self):
        self.assertEqual(game_state.add_gold_card(401), 401)
        self.assertIsNone(game_state.add_gold_card(401))
        self.assertEqual(self.counters(401), (0, 0, 1))
        game_state.gold_cards = [401] * game_state.MAX_GOLD_CARDS
        self.assertIsNone(game_state.add_gold_card(402))
        game_state.gold_cards = []
        # Restoring inventory is not a new acquisition.
        game_state.gold_cards = [401]
        self.assertEqual(self.counters(401), (0, 0, 1))

    def test_multibagger_and_random_reward_are_bonus_sources(self):
        with mock.patch.object(game_state, "build_gold_cards_pool", return_value=[401]), \
             mock.patch.object(game_state, "build_open_gold_cards_pool", return_value=[401]):
            self.assertEqual(game_state.buy_multibagger_gold_card(4), 401)
        self.assertEqual(self.counters(401), (0, 0, 1))
        with mock.patch.object(game_state, "build_gold_cards_pool", return_value=[402]):
            self.assertEqual(game_state.add_random_gold_card(4), 402)
        self.assertEqual(self.counters(402), (0, 0, 1))

    def test_golden_stocks_miss_and_repeated_resolution_do_not_count(self):
        with mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[401]), \
             mock.patch.object(game_state.random, "randint", side_effect=[100, 1]):
            self.assertIsNone(game_state.resolve_golden_stocks_round([302]))
            self.assertFalse(os.path.exists(self.path))
            self.assertEqual(game_state.resolve_golden_stocks_round([302]), 401)
            self.assertIsNone(game_state.resolve_golden_stocks_round([302]))
        self.assertEqual(self.counters(401), (0, 0, 1))

    def test_profile_switch_restart_and_disabled_test_mode(self):
        stats.record_card_acquisitions("offered", [401])
        self.configure(3)
        stats.record_card_acquisitions("purchased", [401])
        self.configure(2)
        stats.record_card_acquisitions("bonus", [401])
        self.assertEqual(self.counters(401), (1, 1, 1))
        self.assertEqual(self.counters(401, 2), (1, 0, 1))
        self.assertEqual(self.counters(401, 3), (0, 1, 0))
        self.configure(2, enabled=False)
        stats.record_card_acquisitions("purchased", [401])
        self.assertEqual(self.counters(401), (1, 1, 1))

    def test_failed_atomic_write_preserves_both_scopes(self):
        stats.record_card_acquisitions("offered", [401])
        with open(self.path, "rb") as source:
            original = source.read()
        with mock.patch("csv_storage.os.replace", side_effect=OSError("locked")), \
             self.assertLogs("card_acquisition_stats", level="ERROR"):
            stats.record_card_acquisitions("purchased", [401])
        with open(self.path, "rb") as source:
            self.assertEqual(original, source.read())


if __name__ == "__main__":
    unittest.main()
