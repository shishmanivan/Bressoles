import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import card_acquisition_stats
import game_state
import game_stats
import profile_manager
from asset_loaders import find_font_path_or_exit
from gameplay_page import GameplayPage


class RoundResultCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.acquisitions = root / "cards.csv"
        self.previous = profile_manager._capture_progress()
        self.addCleanup(profile_manager.apply_profile_to_game_state, {"progress": self.previous})
        for module, name, value in (
            (profile_manager, "PROFILES_DIR", str(root)),
            (profile_manager, "INDEX_FILE", str(root / "index.json")),
            (game_stats, "STATS_FILE", str(root / "stats.csv")),
            (game_stats, "LEVEL6_EXPERIMENT_STATS_FILE", str(root / "experiment.csv")),
            (card_acquisition_stats, "_tracker", card_acquisition_stats.CardAcquisitionStats(
                1, path=self.acquisitions)),
        ):
            setting = patch.object(module, name, value)
            setting.start()
            self.addCleanup(setting.stop)
        pygame.init()
        self.screen = pygame.display.set_mode((1680, 1050))
        self.addCleanup(pygame.quit)
        profile_manager.select_profile(1, "Test")
        game_state.ensure_napoleondor_level(8)
        game_state.silver_cards = [217]
        self.page = self.make_page()
        self.page.Money = 9
        self.page._save_active_game()

    def make_page(self, saved_state=None):
        return GameplayPage(
            self.screen, find_font_path_or_exit(), "e", goal=10, level_number=8,
            round_num=1, boss_index=0, boss_filename="2_AdamSmith.png",
            profile_slot=1, active_silver_cards=[217], saved_state=saved_state,
        )

    def reload_page(self):
        profile = profile_manager.load_profile(1)
        profile_manager.apply_profile_to_game_state(profile)
        return self.make_page(profile["active_game"]["state"])

    def win(self, page):
        # Inject a deterministic gold reward through its real inventory/CSV path.
        with patch.object(page, "_add_reward_card_to_deck",
                          side_effect=lambda: game_state.add_gold_card(401)):
            page.Money = 10
            page._check_win_lose()

    def assert_one_result(self):
        profile = profile_manager.load_profile(1)
        self.assertEqual(profile["active_game"]["state"]["win_lose_state"], "win")
        self.assertTrue(profile["active_game"]["state"]["active_silver_cards_spent"])
        self.assertEqual(profile["progress"]["napoleondors"], 5)
        self.assertEqual(profile["progress"]["silver_cards"], [])
        self.assertEqual(profile["progress"]["gold_cards"], [401])
        for path in (game_stats.STATS_FILE, game_stats.LEVEL6_EXPERIMENT_STATS_FILE):
            rows = game_stats._read_rows(path)
            self.assertEqual([(r["Сыграно"], r["Победы"]) for r in rows], [("1", "1")])
        with self.acquisitions.open(encoding="utf-8-sig", newline="") as source:
            counts = {r["Профиль"]: r["ПолученоБонусом"] for r in csv.DictReader(source, delimiter=";")}
        self.assertEqual(counts, {"Все": "1", "1": "1"})

    def test_interruption_after_obligation_preserves_playable_snapshot(self):
        before = profile_manager.load_profile(1)
        with patch.object(self.page, "_apply_shareholder_base_win_bonus", side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                self.win(self.page)
        self.assertEqual(profile_manager.load_profile(1), before)
        self.assertFalse(self.acquisitions.exists())
        self.assertFalse(game_stats._read_rows())
        self.win(self.reload_page())
        self.assert_one_result()

    def test_interruption_between_primary_and_mirrored_stats_recovers_once(self):
        write_rows = game_stats._write_rows

        def interrupt_mirror(rows, path=None):
            if game_stats._get_active_stats_file(path) == game_stats.LEVEL6_EXPERIMENT_STATS_FILE:
                raise InterruptedError
            return write_rows(rows, path)

        with patch.object(game_stats, "_write_rows", side_effect=interrupt_mirror):
            with self.assertRaises(InterruptedError):
                self.win(self.page)
        self.assertEqual(game_stats._read_rows()[0]["Победы"], "1")
        self.assertFalse(self.acquisitions.exists())
        self.reload_page()
        # Another restart before the next autosave replays the same receipt.
        restored = self.reload_page()
        self.win(restored)
        self.assert_one_result()

    def test_early_victory_publishes_one_complete_profile(self):
        with patch.object(profile_manager, "_save_profile_once",
                          wraps=profile_manager._save_profile_once) as commit:
            self.win(self.page)
            commit.assert_called_once()
        self.assert_one_result()

    def test_failed_profile_replace_preserves_old_result_and_stats(self):
        previous = profile_manager.load_profile(1)
        primary = profile_manager.get_profile_path(1)
        write = profile_manager._write_json_atomically

        def fail_primary(path, data):
            if path == primary:
                raise OSError("interrupted before profile replacement")
            return write(path, data)

        with patch.object(profile_manager, "_write_json_atomically", side_effect=fail_primary):
            with self.assertRaises(OSError):
                self.win(self.page)
        self.assertEqual(profile_manager.load_profile(1), previous)
        self.assertEqual(profile_manager._read_profile_data(primary + ".bak"), previous)
        self.assertFalse(game_stats._read_rows())
        self.assertFalse(self.acquisitions.exists())
        self.win(self.reload_page())
        self.assert_one_result()
