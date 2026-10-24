"""Exercise hooks in child processes so tests do not change the runner's streams."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RuntimeDiagnosticsTests(unittest.TestCase):
    def run_child(self, folder, source):
        env = dict(os.environ, LOCALAPPDATA=str(folder), SDL_VIDEODRIVER="dummy",
                   SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
        return subprocess.run([sys.executable, "-c", source], cwd=ROOT, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)

    def session(self, folder):
        return sorted((Path(folder) / "Bressoles" / "Logs").glob("session-*"))[-1]

    def state(self, session):
        return json.loads((session / "status.json").read_text())["state"]

    def test_clean_exit_captures_console_and_native_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, r"""
from runtime_diagnostics import start_session, finish_session, event
import faulthandler, sys
s = start_session()
assert start_session() is s
print('console output')
sys.stderr.write('warning output\n')
event('startup.test', language='RU')
faulthandler.dump_traceback(file=s.native)
finish_session()
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            session = self.session(folder)
            log = (session / "game.log").read_text(encoding="utf-8")
            for expected in ("console output", "warning output", "startup.test", "session.end"):
                self.assertIn(expected, log)
            self.assertIn("console output", result.stdout)
            self.assertEqual(self.state(session), "completed")
            self.assertIn('File "<string>"', (session / "native-crash.log").read_text())

    def test_uncaught_exception_has_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, "from runtime_diagnostics import start_session, event; start_session(); event('before.failure'); raise ValueError('diagnostic test')")
            self.assertNotEqual(result.returncode, 0)
            session = self.session(folder)
            log = (session / "game.log").read_text(encoding="utf-8")
            self.assertIn("Traceback", log)
            self.assertIn("ValueError: diagnostic test", log)
            self.assertIn("before.failure", log)
            self.assertEqual(self.state(session), "crashed")

    def test_thread_exception_is_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, """
from runtime_diagnostics import start_session, finish_session
import threading
start_session()
def fail():
    raise RuntimeError('worker failed')
t = threading.Thread(target=fail, name='test-worker')
t.start()
t.join()
finish_session()
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            session = self.session(folder)
            self.assertEqual(self.state(session), "completed_with_errors")
            self.assertIn("worker failed", (session / "game.log").read_text())

    def test_abrupt_exit_preserves_last_event_without_clean_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, "from runtime_diagnostics import start_session, event; import os; start_session(); event('before.hard.exit'); os._exit(7)")
            self.assertEqual(result.returncode, 7)
            session = self.session(folder)
            self.assertEqual(self.state(session), "running")
            self.assertIn("before.hard.exit", (session / "game.log").read_text())

    def test_retention_and_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "Bressoles" / "Logs"
            for index in range(12):
                old = root / f"session-20000101T000000.{index:06d}Z-1"
                old.mkdir(parents=True)
                (old / "game.log").write_text("old")
            result = self.run_child(folder, """
from runtime_diagnostics import start_session, finish_session, event
s = start_session()
s.handler.maxBytes = 256
for i in range(100):
    event('rotation', index=i, detail='x' * 100)
finish_session()
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list(root.glob("session-*"))), 10)
            session = self.session(folder)
            self.assertEqual(len(list(session.glob("game.log*"))), 3)
            self.assertIn("session.end", (session / "game.log").read_text())

    def test_main_import_failure_is_captured_before_pygame_load(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, "import sys, runpy; sys.modules['pygame'] = None; runpy.run_path('Main.py', run_name='__main__')")
            self.assertNotEqual(result.returncode, 0)
            session = self.session(folder)
            self.assertEqual(self.state(session), "crashed")
            self.assertIn("ModuleNotFoundError", (session / "game.log").read_text())

    def test_main_starts_and_quits_with_dummy_display(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, """
from runtime_diagnostics import start_session, finish_session
start_session()
import Main, pygame, profile_manager, os
profile_manager.PROFILES_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'test-profiles')
profile_manager.INDEX_FILE = os.path.join(profile_manager.PROFILES_DIR, 'index.json')
pygame.event.post(pygame.event.Event(pygame.QUIT))
try:
    Main.main()
except SystemExit as exc:
    finish_session(exc.code)
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            session = self.session(folder)
            self.assertEqual(self.state(session), "completed")
            self.assertIn("startup.profile.loaded", (session / "game.log").read_text(encoding="utf-8"))

    def test_log_write_failure_does_not_recurse_or_crash_game(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, """
from runtime_diagnostics import start_session, finish_session, event
from unittest.mock import patch
s = start_session()
with patch.object(s.handler, 'shouldRollover', side_effect=OSError('disk full')):
    event('cannot.write')
    print('game still running')
finish_session()
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("game still running", result.stdout)

    def test_unwritable_log_folder_does_not_stop_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_child(folder, """
from runtime_diagnostics import start_session
from pathlib import Path
from unittest.mock import patch
with patch.object(Path, 'mkdir', side_effect=PermissionError('read only')):
    assert start_session() is None
print('startup continues')
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("startup continues", result.stdout)
            self.assertIn("could not create diagnostic logs", result.stderr)


if __name__ == "__main__":
    unittest.main()
