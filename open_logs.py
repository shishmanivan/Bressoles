"""Open Bressoles diagnostic logs without starting pygame."""
import os
from pathlib import Path
import tempfile

from runtime_diagnostics import logs_directory


if __name__ == "__main__":
    path = logs_directory()
    fallback = Path(tempfile.gettempdir()) / "Bressoles" / "Logs"
    print(f"Bressoles logs: {path}")
    if fallback.exists():
        print(f"Fallback logs: {fallback}")
    if os.name == "nt":
        if path.exists():
            os.startfile(path)
        if fallback.exists():
            os.startfile(fallback)
