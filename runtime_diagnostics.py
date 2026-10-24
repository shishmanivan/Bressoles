"""Local, bounded diagnostics. Importing this module has no side effects."""
import atexit
from datetime import datetime, timezone
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading


logger = logging.getLogger("bressoles")
logger.addHandler(logging.NullHandler())
_session = None


def logs_directory():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state")) / "Bressoles" / "Logs"


def event(stage, **details):
    logger.info("%s %s", stage, json.dumps(details, ensure_ascii=False, default=str))


def gameplay_event(stage, page):
    fields = ("level_number", "round_num", "boss_filename", "difficulty", "Day",
              "LastTurn", "Money", "Goal", "Aprice", "BPrice", "CPrice",
              "Aquantity", "Bquantity", "Cquantity", "market_cards", "side_cards_top")
    event(stage, **{key: getattr(page, key, None) for key in fields})


def run_page(page):
    name = type(page).__name__
    event("screen.enter", screen=name)
    result = page.run()
    # Do not record profiles, names or entire save states returned by screens.
    event("screen.leave", screen=name, result=result if isinstance(result, (str, int, type(None))) else type(result).__name__)
    return result


class _Tee:
    def __init__(self, original, level):
        self.original = original
        self.level = level
        self.pending = ""
        self.lock = threading.RLock()

    def write(self, text):
        with self.lock:
            self.pending += text
            while "\n" in self.pending or len(self.pending) > 4096:
                if "\n" in self.pending:
                    line, self.pending = self.pending.split("\n", 1)
                else:
                    line, self.pending = self.pending[:4096], self.pending[4096:]
                if line.strip():
                    logger.log(self.level, "%s", line.rstrip())
            if self.original is not None:
                try:
                    self.original.write(text)
                except (OSError, ValueError, UnicodeError):
                    pass
        return len(text)

    def flush(self):
        with self.lock:
            if self.pending:
                logger.log(self.level, "%s", self.pending)
                self.pending = ""
            if self.original is not None:
                try:
                    self.original.flush()
                except (OSError, ValueError):
                    pass

    def __getattr__(self, name):
        return getattr(self.original, name)


class _SafeRotatingHandler(RotatingFileHandler):
    def handleError(self, record):
        # A full/removed disk must not recurse through our captured stderr.
        pass


class Session:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("session-%Y%m%dT%H%M%S.%fZ-") + str(os.getpid())
        self.path = root / name
        self.path.mkdir()
        self.handler = _SafeRotatingHandler(self.path / "game.log", maxBytes=2 * 1024 * 1024,
                                           backupCount=2, encoding="utf-8")
        try:
            self.native = (self.path / "native-crash.log").open("w", encoding="utf-8")
        except OSError:
            self.handler.close()
            raise
        self.failed = False
        self.finished = False
        self.status("running")

    def status(self, state):
        try:
            temporary = self.path / "status.tmp"
            temporary.write_text(json.dumps({"state": state, "pid": os.getpid(),
                                            "updated_utc": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
            temporary.replace(self.path / "status.json")
        except OSError:
            pass

    def exception(self, exc_type, exc_value, traceback, source="main"):
        self.failed = True
        logger.critical("Unhandled exception (%s)", source, exc_info=(exc_type, exc_value, traceback))
        self.status("crashed" if source == "main" else "running_with_errors")

    def finish(self, code=0):
        self.finished = True
        event("session.end", exit_code=code)
        if code not in (0, None):
            self.status("failed_exit")
        else:
            self.status("completed_with_errors" if self.failed else "completed")

    def at_exit(self):
        sys.stdout.flush()
        sys.stderr.flush()
        if not self.finished and not self.failed:
            event("session.incomplete", reason="Exited before normal shutdown")
            self.status("incomplete")
        try:
            self.handler.flush()
        except OSError:
            pass
        # Keep the native descriptor open until process exit: late C crashes matter.


def _prune(root):
    sessions = sorted(root.glob("session-*"), reverse=True)
    for old in sessions[10:]:
        if not old.is_dir() or old.is_symlink():
            continue
        try:
            # Only our known files; never recursively remove arbitrary contents.
            for name in ("game.log", "game.log.1", "game.log.2", "native-crash.log", "status.json", "status.tmp"):
                (old / name).unlink(missing_ok=True)
            old.rmdir()
        except OSError:
            pass  # e.g. another game process still owns this log on Windows


def start_session(root=None):
    global _session
    if _session is not None:
        return _session
    candidates = [Path(root)] if root is not None else [logs_directory(), Path(tempfile.gettempdir()) / "Bressoles" / "Logs"]
    for candidate in candidates:
        try:
            session = Session(candidate)
            break
        except OSError:
            continue
    else:
        if sys.stderr:
            sys.stderr.write("Bressoles: could not create diagnostic logs.\n")
        return None
    _session = session
    session.handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(session.handler)
    logger.propagate = False
    sys.stdout = _Tee(sys.stdout, logging.INFO)
    sys.stderr = _Tee(sys.stderr, logging.ERROR)
    previous_hook = sys.excepthook

    def exception_hook(kind, value, tb):
        session.exception(kind, value, tb)
        previous_hook(kind, value, tb)

    sys.excepthook = exception_hook
    previous_thread_hook = threading.excepthook

    def thread_hook(args):
        session.exception(args.exc_type, args.exc_value, args.exc_traceback, "thread:" + args.thread.name)
        previous_thread_hook(args)

    threading.excepthook = thread_hook
    try:
        faulthandler.enable(file=session.native, all_threads=True)
    except (OSError, RuntimeError):
        logger.exception("Native crash handler unavailable")
    atexit.register(session.at_exit)
    event("session.start", log_directory=str(session.path), python=sys.version,
          platform=platform.platform(), architecture=platform.machine(), cwd=os.getcwd())
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                                  capture_output=True, text=True, timeout=2,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        event("build", git_commit=revision.stdout.strip() if revision.returncode == 0 else "unavailable")
    except (OSError, subprocess.TimeoutExpired):
        event("build", git_commit="unavailable")
    _prune(candidate)
    return session


def finish_session(code=0):
    if _session is not None:
        _session.finish(code)
