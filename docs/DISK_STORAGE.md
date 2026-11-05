# Disk access and persistence

Use `disk_storage` for game data I/O. Do not retry gameplay actions: they can
award cards, increment counters, or consume randomness more than once.

- `atomic_write` / `write_json`: serialize a fixed snapshot, write and fsync a
  sibling temporary file, then replace the destination. Old data survives a
  failed write. Five attempts use bounded backoff; the application retry dialog
  handles persistent errors and keeps the pending operation alive.
- `csv_storage.write_semicolon_csv_atomically`: the same path for every CSV
  snapshot, including the market journal. Do not retry append operations: a
  failed flush can already have appended some of the bytes.
- `read_text` / `open_text`: finish reading before giving data to the caller.
  Access errors must not be interpreted as an empty save. Missing optional files
  retain FileNotFoundError semantics so existing creation/default rules apply.
- `ensure_directory` and `disk_operation`: directory creation/deletion and other
  idempotent filesystem operations. Never wrap a whole game action here.
- `game_stats.statistics_transaction`: related counters are staged in memory
  and written once per statistics file. This is not a multi-file transaction.

Main installs the common error handler before loading game modules. The recovery
screen uses the built-in font and literal text, so showing it needs no assets or
translation files from the failing disk. An unfinished payload stays in memory;
if preparation succeeded, its temporary file remains available while waiting.
When no UI handler is installed (tests/tools), failures propagate after retries.

Profile saves retain their existing full-profile emergency snapshot and backup
validation above the shared writer. Corrupt profiles must never be overwritten.
Diagnostic logs remain best-effort and do not open a retry dialog: a logging
failure must not recurse while reporting another storage failure. Optional
media retain their existing fallback behavior.

Regression coverage: tests/test_disk_storage.py, test_profile_recovery.py,
test_stats_contract.py, test_market_roll_stats.py, test_card_acquisition_stats.py.
