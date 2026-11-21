"""Disk operations: retry I/O, never replay a gameplay action.

Install error_handler in the application to keep pending work alive while the
player releases a lock/frees disk space. Headless callers receive the error.
"""
import errno
import io
import json
import logging
import os
import tempfile
import time

error_handler = None
logger = logging.getLogger("bressoles")


def lock_file_handle(handle, *, wait):
    """Hold an OS lock on a stable sidecar until the open handle is closed."""
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        if not wait:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        # LK_LOCK sleeps a full second even when a journal append takes only
        # milliseconds. Keep its ten-second bound while waking up promptly.
        deadline = time.monotonic() + 10
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    else:
        import fcntl
        flags = fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB
        fcntl.flock(handle, flags)


def disk_operation(operation, *, interactive=True, recovery_path=None, missing_ok=False):
    while True:
        for attempt in range(5):
            try:
                return operation()
            except OSError as error:
                if missing_ok and isinstance(error, FileNotFoundError):
                    raise
                if attempt < 4:
                    time.sleep(0.05 * 2 ** attempt)
                    continue
                if not interactive or error_handler is None:
                    raise
                logger.warning("Disk operation failed; waiting for retry: %s", error)
                error_handler(error, recovery_path)


def read_text(path, encoding="utf-8", *, missing_ok=True):
    def read():
        with open(path, encoding=encoding, newline="") as source:
            return source.read()
    return disk_operation(read, missing_ok=missing_ok)


def open_text(path, mode="r", encoding="utf-8", newline=None):
    """Read completely before exposing data, so read failures are retryable."""
    if mode != "r":
        raise ValueError("open_text only supports reading")
    return io.StringIO(read_text(path, encoding), newline=newline)


def exists(path):
    """Access denied is not evidence that a save does not exist."""
    try:
        disk_operation(lambda: os.stat(path), missing_ok=True)
        return True
    except FileNotFoundError:
        return False


def ensure_directory(path):
    return disk_operation(lambda: os.makedirs(path, exist_ok=True))


def atomic_write(path, payload, *, interactive=True):
    """Commit immutable bytes. A failed commit keeps a complete pending file."""
    path = os.fspath(path)
    directory = os.path.dirname(path) or "."
    pending = None
    def prepare():
        nonlocal pending
        os.makedirs(directory, exist_ok=True)
        descriptor, candidate = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            try:
                os.remove(candidate)
            except OSError:
                pass
            raise
        pending = candidate
    disk_operation(prepare, interactive=interactive)
    try:
        disk_operation(lambda: os.replace(pending, path), interactive=interactive,
                       recovery_path=pending)
    except OSError:
        # Without a UI, retain the previous API's cleanup contract.
        try:
            os.remove(pending)
        except OSError:
            pass
        raise


def write_json(path, data, *, interactive=True):
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    atomic_write(path, payload, interactive=interactive)
