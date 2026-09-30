import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import profile_manager as pm
import game_stats
from profile_page import ProfilePage
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate


class ProfileDeletionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for field, value in (("PROFILES_DIR", temporary.name),
                             ("INDEX_FILE", str(self.directory / "index.json")),
                             ("_recovered_profile_paths", set())):
            patch = mock.patch.object(pm, field, value)
            patch.start()
            self.addCleanup(patch.stop)
        profile = pm._default_profile(1)
        profile.update(name="Old", tutorial_seen=["stock_cards", "sell_before_last_turn"])
        profile["progress"]["level_1_boss_defeated"] = True
        pm.save_profile(profile)
        pm.set_selected_slot(1)

    def test_delete_and_recreate_preserves_all_statistics_and_other_profiles(self):
        pm.save_profile(pm._default_profile(2))
        other = Path(pm.get_profile_path(2)).read_bytes()
        paths = [pm.get_stats_file(1), pm.get_level6_experiment_stats_file(1),
                 pm.get_shop_card_stats_file(1), str(self.directory / "CardAcquisitionStats.csv")]
        for path in paths:
            Path(path).write_bytes(b"wins;losses\n12;7\n")
        pm.delete_profile(1)
        self.assertIsNone(pm.get_selected_slot())
        self.assertFalse(Path(pm.get_profile_path(1)).exists())
        self.assertFalse(Path(pm.get_profile_path(1) + ".bak").exists())
        fresh = pm.load_profile(1)
        self.assertEqual(fresh["tutorial_seen"], [])
        self.assertFalse(fresh["progress"]["level_1_boss_defeated"])
        with mock.patch.object(pm, "apply_profile_to_game_state"):
            pm.select_profile(1, "New")
        for path in paths:
            self.assertEqual(Path(path).read_bytes(), b"wins;losses\n12;7\n")
        self.assertEqual(Path(pm.get_profile_path(2)).read_bytes(), other)

    def test_backup_only_and_corrupt_profiles_can_be_deleted(self):
        for backup_only in (True, False):
            path = Path(pm.get_profile_path(1))
            if path.exists():
                path.unlink()
            if not backup_only:
                path.write_bytes(b"broken")
            Path(str(path) + ".bak").write_bytes(b"broken backup")
            pm.delete_profile(1)
            self.assertEqual(pm.load_profile(1), pm._default_profile(1))

    def test_reused_slot_continues_existing_win_loss_counters(self):
        with mock.patch.object(game_stats, "STATS_FILE", pm.get_stats_file(1)), mock.patch.object(
            game_stats, "_ACTIVE_STATS_FILE", None
        ), mock.patch.object(pm, "apply_profile_to_game_state"):
            game_stats.ensure_stats_file()
            game_stats.update_game_stats(1, 1, "Boss", True)
            game_stats.update_game_stats(1, 1, "Boss", False)
            pm.delete_profile(1)
            pm.select_profile(1, "New")
            game_stats.set_stats_file(pm.get_stats_file(1))
            game_stats.update_game_stats(1, 1, "Boss", True)
            row = game_stats._read_rows()[0]
            self.assertEqual((row["Сыграно"], row["Победы"], row["Поражения"]), ("3", "2", "1"))

    def test_cross_requires_yes_and_blocks_underlying_profile_controls(self):
        pygame.init()
        self.addCleanup(pygame.quit)
        page = ProfilePage(pygame.display.set_mode((1680, 1050)), None,
                           "egyptiennemncyr_condensedbold.ttf")
        def click(rect):
            with mock.patch.object(pygame.event, "get", return_value=[
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
            ]):
                page.handle_input()
        click(page.delete_rects[0])
        self.assertEqual(page.deleting_slot, 1)
        click(page.button_rects[1])
        self.assertIsNone(page.editing_slot)
        click(page.delete_no_rect)
        self.assertTrue(Path(pm.get_profile_path(1)).exists())
        click(page.delete_rects[0])
        click(page.delete_yes_rect)
        self.assertFalse(Path(pm.get_profile_path(1)).exists())
        self.assertNotIn(1, page.occupied_slots)
        self.assertIsNone(page.selected_slot)
        click(page.button_rects[0])
        self.assertEqual(page.editing_slot, 1)

    def test_confirmation_is_localized(self):
        original = get_language()
        self.addCleanup(set_language, original)
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            for text in ("Удалить профиль {slot}?", "Это действие нельзя отменить.",
                         "Да", "Нет",
                         "Не удалось удалить профиль. Попробуйте ещё раз."):
                if language != "RU":
                    self.assertNotRegex(translate(text), r"[А-Яа-яЁё]")

    def test_failed_backup_removal_keeps_primary_and_reports_failure(self):
        before = Path(pm.get_profile_path(1)).read_bytes()
        with mock.patch.object(pm.os, "remove", side_effect=PermissionError("denied")):
            with self.assertRaises(OSError):
                pm.delete_profile(1)
        self.assertEqual(Path(pm.get_profile_path(1)).read_bytes(), before)
