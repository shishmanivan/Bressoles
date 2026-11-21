import multiprocessing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import game_state
import profile_manager as pm
from profile_page import ProfilePage


def _play_until_victory(directory, connection):
    pm.PROFILES_DIR = directory
    pm.INDEX_FILE = str(Path(directory) / "index.json")
    with connection, pm.ProfileSession() as session:
        session.activate(1, pm.select_profile, "Winner")
        game_state.level_1_boss_defeated = True
        pm.save_progress_from_game_state(1)
        pm.clear_active_game(1)
        connection.send("victory saved")
        connection.recv()


class ProfileSessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        for key, value in (("PROFILES_DIR", temp.name), ("INDEX_FILE", str(self.directory / "index.json"))):
            override = patch.object(pm, key, value)
            override.start()
            self.addCleanup(override.stop)
        self.addCleanup(pm.apply_profile_to_game_state, pm._default_profile(1))

    def open_winning_game(self):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        self.addCleanup(parent.close)
        process = context.Process(target=_play_until_victory, args=(str(self.directory), child))
        process.start()
        child.close()

        def stop():
            if process.is_alive():
                process.terminate()
            process.join(10)
            process.close()

        self.addCleanup(stop)
        self.assertTrue(parent.poll(20), "Game did not save the victory")
        self.assertEqual(parent.recv(), "victory saved")
        return process, parent

    def test_stale_window_cannot_overwrite_victory_or_delete_busy_slot(self):
        stale = pm.select_profile(1, "Before victory")
        process, connection = self.open_winning_game()
        files = [self.directory / name for name in ("profile_1.json", "profile_1.json.bak")]
        saved = [path.read_bytes() for path in files]
        with pm.ProfileSession() as other:
            other.activate(2, pm.select_profile, "Independent")
            for operation in (
                lambda: pm.save_active_game(1, {"level_number": 1}, {"Day": 3}),
                lambda: pm.save_profile(stale),
                lambda: pm.delete_profile(1),
                lambda: other.activate(1, pm.select_profile, "Renamed"),
            ):
                with self.assertRaises(pm.ProfileBusyError):
                    operation()
            self.assertEqual(other.slot, 2)
            pm.save_active_game(2, {"level_number": 1}, {"Day": 9})
            self.assertEqual(pm.get_active_game(2)["state"]["Day"], 9)
            self.assertEqual([path.read_bytes() for path in files], saved)

            page = ProfilePage.__new__(ProfilePage)
            page.session, page.lang = other, {}
            page.profiles = pm.list_profiles()
            page._start_editing(1)
            self.assertIsNone(page.editing_slot)
            self.assertIn("другом окне", page.status_message)
            connection.send("exit")
            process.join(10)
            self.assertEqual(process.exitcode, 0)
            page._start_editing(1)
            self.assertEqual(page.input_text, "Winner")
            self.assertEqual(page._confirm_selection()["slot"], 1)
            self.assertEqual(other.slot, 1)
            self.assertTrue(game_state.level_1_boss_defeated)
            self.assertIsNone(pm.get_active_game(1))

    def test_terminated_process_releases_slot_without_manual_cleanup(self):
        process, _ = self.open_winning_game()
        process.terminate()
        process.join(10)
        self.assertFalse(process.is_alive())
        with pm.ProfileSession() as session:
            saved = session.activate(1, pm.load_profile)
            self.assertTrue(saved["progress"]["level_1_boss_defeated"])
            self.assertIsNone(saved["active_game"])
