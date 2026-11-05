import csv
import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import disk_storage
import game_stats
from csv_storage import write_semicolon_csv_atomically


class DiskStorageTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "stats.csv"
        for name, value in (("error_handler", None),):
            patch = mock.patch.object(disk_storage, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(disk_storage.time, "sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def test_transient_replace_retries_same_generator_without_duplicate_rows(self):
        original = os.replace
        attempts = []
        def replace(source, target):
            attempts.append(source)
            if len(attempts) < 3:
                raise PermissionError("busy")
            original(source, target)
        with mock.patch.object(disk_storage.os, "replace", side_effect=replace):
            write_semicolon_csv_atomically(self.path, ["count"], ({"count": n} for n in [1, 2]))
        self.assertEqual(len(set(attempts)), 1)
        with self.path.open(encoding="utf-8-sig") as source:
            self.assertEqual(list(csv.DictReader(source, delimiter=";")), [{"count": "1"}, {"count": "2"}])

    def test_persistent_lock_keeps_old_file_and_pending_bytes_until_retry(self):
        self.path.write_bytes(b"old")
        original = os.replace
        locked = True
        def replace(source, target):
            if locked:
                raise PermissionError("busy")
            original(source, target)
        def retry(error, recovery):
            nonlocal locked
            self.assertEqual(self.path.read_bytes(), b"old")
            self.assertEqual(Path(recovery).read_bytes(), b"new")
            locked = False
        with mock.patch.object(disk_storage.os, "replace", side_effect=replace), mock.patch.object(disk_storage, "error_handler", side_effect=retry) as handler:
            disk_storage.atomic_write(self.path, b"new")
        handler.assert_called_once()
        self.assertEqual(self.path.read_bytes(), b"new")
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_disk_full_during_flush_preserves_old_file_then_retries(self):
        self.path.write_bytes(b"old")
        original = os.fsync
        blocked = True
        def flush(fd):
            if blocked:
                raise OSError(errno.ENOSPC, "full")
            original(fd)
        def retry(error, recovery):
            nonlocal blocked
            self.assertIsNone(recovery)
            self.assertEqual(self.path.read_bytes(), b"old")
            blocked = False
        with mock.patch.object(disk_storage.os, "fsync", side_effect=flush), mock.patch.object(disk_storage, "error_handler", side_effect=retry):
            disk_storage.atomic_write(self.path, b"new")
        self.assertEqual(self.path.read_bytes(), b"new")
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_settings_read_denial_does_not_erase_unrelated_values(self):
        import app_settings
        self.path.write_text(json.dumps({"language": "EN", "music_volume": 0.4}))
        original = open
        locked = True
        def read(*args, **kwargs):
            if locked:
                raise PermissionError("busy")
            return original(*args, **kwargs)
        def retry(error, recovery):
            nonlocal locked
            locked = False
        with mock.patch.object(disk_storage, "open", side_effect=read, create=True), mock.patch.object(disk_storage, "error_handler", side_effect=retry):
            app_settings.save_music_volume(0.8, self.path)
        self.assertEqual(json.loads(self.path.read_text()), {"language": "EN", "music_volume": 0.8})

    def test_transaction_commits_all_defeat_counters_once(self):
        with mock.patch.object(game_stats, "STATS_FILE", str(self.path)), mock.patch.object(game_stats, "LEVEL6_EXPERIMENT_STATS_FILE", None):
            game_stats.update_level_run_started(5)
            original = os.replace
            attempts = 0
            def replace(source, target):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError("busy")
                original(source, target)
            with mock.patch.object(disk_storage.os, "replace", side_effect=replace):
                with game_stats.statistics_transaction():
                    game_stats.update_level_boss_position_stats(5, 1, False)
                    game_stats.update_level_run_loss_stage_stats(5, "Босс уровня 1", 1)
                    game_stats.update_level_run_result(5, False)
            self.assertEqual(attempts, 3)
            self.assertEqual(game_stats.get_level_run_losses(5), 1)
            rows = game_stats._read_rows()
            self.assertEqual(sum(int(row["Поражения"]) for row in rows), 3)

    def test_missing_read_keeps_missing_file_semantics(self):
        with mock.patch.object(disk_storage, "error_handler") as handler:
            with self.assertRaises(FileNotFoundError):
                disk_storage.read_text(self.path)
        handler.assert_not_called()

    def test_directory_creation_denial_waits_then_writes(self):
        original = os.makedirs
        blocked = True
        def mkdir(*args, **kwargs):
            if blocked:
                raise PermissionError("directory busy")
            return original(*args, **kwargs)
        def retry(error, recovery):
            nonlocal blocked
            blocked = False
        with mock.patch.object(disk_storage.os, "makedirs", side_effect=mkdir), mock.patch.object(disk_storage, "error_handler", side_effect=retry):
            disk_storage.atomic_write(self.path, b"new")
        self.assertEqual(self.path.read_bytes(), b"new")

    def test_denied_stat_is_not_treated_as_missing_save(self):
        self.path.write_bytes(b"existing")
        original = os.stat
        blocked = True
        def stat(*args, **kwargs):
            if blocked:
                raise PermissionError("busy")
            return original(*args, **kwargs)
        def retry(error, recovery):
            nonlocal blocked
            blocked = False
        with mock.patch.object(disk_storage.os, "stat", side_effect=stat), mock.patch.object(disk_storage, "error_handler", side_effect=retry):
            self.assertTrue(disk_storage.exists(self.path))
