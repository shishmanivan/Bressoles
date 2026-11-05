import csv
import io

from disk_storage import atomic_write


def write_semicolon_csv_atomically(path, fieldnames, rows):
    """Serialize once; retries cannot consume rows or increment counters twice."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, output.getvalue().encode("utf-8-sig"))
