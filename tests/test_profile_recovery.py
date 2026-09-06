import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import profile_manager
from profile_page import ProfilePage


class ProfileRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for field, value in (
            ("PROFILES_DIR", str(self.directory)),
            ("INDEX_FILE", str(self.directory / "index.json")),
            ("_recovered_profile_paths", set()),
        ):
            patch = mock.patch.object(profile_manager, field, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.primary = Path(profile_manager.get_profile_path(1))
        self.backup = Path(str(self.primary) + ".bak")
        self.profile = profile_manager._default_profile(1)
        self.profile["name"] = "Saved campaign"
        self.profile["progress"]["level_1_boss_defeated"] = True
        self.profile["active_game"] = {
            "context": {"level_number": 2},
            "state": {"Day": 4, "Money": 75},
        }

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write_backup(self):
        self.backup.write_text(json.dumps(self.profile), encoding="utf-8")

    def test_absent_files_are_a_new_slot_without_writes(self):
        profile = profile_manager.load_profile(1)
        self.assertEqual(profile["name"], "")
        self.assertFalse(profile["progress"]["level_1_boss_defeated"])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_first_save_has_backup_and_next_save_keeps_previous_progress(self):
        profile_manager.save_profile(self.profile)
        self.assertEqual(self.read(self.primary), self.profile)
        self.assertEqual(self.read(self.backup), self.profile)
        updated = copy.deepcopy(self.profile)
        updated["active_game"]["state"]["Day"] = 5
        profile_manager.save_profile(updated)
        self.assertEqual(self.read(self.primary), updated)
        self.assertEqual(self.read(self.backup), self.profile)

    def test_invalid_json_encoding_and_envelope_restore_backup_and_archive_bytes(self):
        for damaged in (b'{"progress":', b'\xff\xfe', b'[]', b'{}',
                        b'{"progress": []}', b'{"progress": {}, "active_game": []}',
                        b'{"progress": {"napoleondors": "broken"}}',
                        b'{"progress": {"silver_cards": 42}}',
                        b'{"progress": {"boss_progress": {"1": "broken"}}}',
                        b'{"progress": {"napoleondors": NaN}}'):
            with self.subTest(damaged=damaged):
                self.write_backup()
                self.primary.write_bytes(damaged)
                before = set(self.directory.glob("*.corrupt-*.bak"))
                restored = profile_manager.load_profile(1)
                self.assertEqual(restored, self.profile)
                self.assertEqual(self.read(self.primary), self.profile)
                self.assertEqual(self.read(self.backup), self.profile)
                archived = set(self.directory.glob("*.corrupt-*.bak")) - before
                self.assertEqual(len(archived), 1)
                self.assertEqual(archived.pop().read_bytes(), damaged)
                self.assertTrue(profile_manager.was_profile_recovered(1))
                profile_manager.load_profile(1)
                self.assertEqual(len(set(self.directory.glob("*.corrupt-*.bak")) - before), 1)

    def test_missing_primary_is_restored_from_backup(self):
        self.write_backup()
        self.assertEqual(profile_manager.load_profile(1), self.profile)
        self.assertEqual(self.read(self.primary), self.profile)

    def test_missing_primary_with_invalid_backup_is_not_a_new_slot(self):
        self.backup.write_bytes(b'broken')
        with self.assertRaises(profile_manager.ProfileLoadError):
            profile_manager.load_profile(1)
        with self.assertRaises(profile_manager.ProfileLoadError):
            profile_manager.save_profile(self.profile)
        self.assertFalse(self.primary.exists())
        self.assertEqual(self.backup.read_bytes(), b'broken')

    def test_unrecoverable_profile_is_preserved_and_all_save_routes_refuse_it(self):
        self.primary.write_bytes(b'broken primary')
        for backup_bytes in (None, b'broken backup'):
            with self.subTest(backup=backup_bytes):
                if backup_bytes:
                    self.backup.write_bytes(backup_bytes)
                for action in (
                    lambda: profile_manager.load_profile(1),
                    lambda: profile_manager.save_profile(self.profile),
                    lambda: profile_manager.select_profile(1, "Replacement"),
                    lambda: profile_manager.save_progress_from_game_state(1),
                    lambda: profile_manager.save_active_game(1, {}, {}),
                    lambda: profile_manager.clear_active_game(1),
                ):
                    with self.assertRaises(profile_manager.ProfileLoadError):
                        action()
                    self.assertEqual(self.primary.read_bytes(), b'broken primary')
                if backup_bytes:
                    self.assertEqual(self.backup.read_bytes(), backup_bytes)

    def test_listing_keeps_other_slots_available_and_error_stub_cannot_be_saved(self):
        self.primary.write_bytes(b'broken')
        profiles = profile_manager.list_profiles()
        self.assertEqual(len(profiles), 4)
        self.assertTrue(profiles[0]["_load_error"])
        self.assertNotIn("_load_error", profiles[1])
        with self.assertRaises(ValueError):
            profile_manager.save_profile(profiles[0])
        self.assertEqual(self.primary.read_bytes(), b'broken')

    def test_access_error_does_not_trigger_recovery_or_change_files(self):
        profile_manager.save_profile(self.profile)
        before = self.primary.read_bytes()
        reader = profile_manager._read_profile_data

        def denied(path):
            if path == str(self.primary):
                raise PermissionError("access denied")
            return reader(path)

        with mock.patch.object(profile_manager, "_read_profile_data", side_effect=denied):
            with self.assertRaises(profile_manager.ProfileLoadError):
                profile_manager.load_profile(1)
        self.assertEqual(self.primary.read_bytes(), before)
        self.assertFalse(profile_manager.was_profile_recovered(1))

    def test_failed_archive_does_not_replace_damaged_primary(self):
        self.primary.write_bytes(b'broken')
        self.write_backup()
        with mock.patch.object(profile_manager.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(profile_manager.ProfileLoadError):
                profile_manager.load_profile(1)
        self.assertEqual(self.primary.read_bytes(), b'broken')
        self.assertEqual(self.read(self.backup), self.profile)
        self.assertEqual(list(self.directory.glob("*.corrupt-*.bak")), [])

    def test_failed_recovery_replace_preserves_primary_backup_and_archive(self):
        self.primary.write_bytes(b'broken')
        self.write_backup()
        with mock.patch.object(profile_manager.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(profile_manager.ProfileLoadError):
                profile_manager.load_profile(1)
        self.assertEqual(self.primary.read_bytes(), b'broken')
        self.assertEqual(self.read(self.backup), self.profile)
        self.assertEqual(next(self.directory.glob("*.corrupt-*.bak")).read_bytes(), b'broken')
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_failed_primary_save_after_backup_keeps_previous_save_readable(self):
        profile_manager.save_profile(self.profile)
        replace = profile_manager.os.replace

        def fail_primary(source, target):
            if target == str(self.primary):
                raise OSError("primary replacement failed")
            return replace(source, target)

        updated = copy.deepcopy(self.profile)
        updated["name"] = "New name"
        with mock.patch.object(profile_manager.os, "replace", side_effect=fail_primary):
            with self.assertRaises(OSError):
                profile_manager.save_profile(updated)
        self.assertEqual(self.read(self.primary), self.profile)
        self.assertEqual(self.read(self.backup), self.profile)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_recovered_legacy_profile_runs_migrations_without_losing_backup(self):
        legacy = {"version": 1, "progress": {"napoleondor_level": 4}, "active_game": None}
        self.backup.write_text(json.dumps(legacy), encoding="utf-8")
        self.primary.write_bytes(b'broken')
        restored = profile_manager.load_profile(1)
        self.assertEqual(restored["version"], 2)
        self.assertEqual(restored["progress"]["napoleondor_level"], 5)
        self.assertEqual(self.read(self.backup), legacy)
        self.assertEqual(self.read(self.primary), restored)

    def test_valid_primary_does_not_depend_on_a_damaged_backup(self):
        profile_manager.save_profile(self.profile)
        self.backup.write_bytes(b'broken backup')
        self.assertEqual(profile_manager.load_profile(1), self.profile)
        profile_manager.save_profile(self.profile)
        self.assertEqual(self.read(self.backup), self.profile)

    def test_bad_new_data_is_rejected_before_replacing_good_files(self):
        profile_manager.save_profile(self.profile)
        updated = copy.deepcopy(self.profile)
        updated["progress"]["napoleondors"] = "broken"
        with self.assertRaises(ValueError):
            profile_manager.save_profile(updated)
        self.assertEqual(self.read(self.primary), self.profile)
        self.assertEqual(self.read(self.backup), self.profile)

    def test_profile_page_blocks_bad_slot_and_can_select_a_different_slot(self):
        self.primary.write_bytes(b'broken')
        page = ProfilePage.__new__(ProfilePage)
        page.lang = {}
        page.profiles = profile_manager.list_profiles()
        page._start_editing(1)
        self.assertIsNone(page.editing_slot)
        self.assertIn("1", page.status_message)
        self.assertIsNone(page._confirm_selection())
        page._start_editing(2)
        self.assertEqual(page.editing_slot, 2)
        self.assertEqual(page.status_message, "")
        with mock.patch.object(profile_manager, "apply_profile_to_game_state"):
            self.assertEqual(page._confirm_selection()["slot"], 2)
        self.assertEqual(self.primary.read_bytes(), b'broken')


if __name__ == "__main__":
    unittest.main()
