import csv
import os
import tempfile


def write_semicolon_csv_atomically(path, fieldnames, rows):
    """Write a semicolon-delimited CSV without exposing a partial target file."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8-sig", newline="") as stats_file:
            writer = csv.DictWriter(stats_file, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
            stats_file.flush()
            os.fsync(stats_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise
