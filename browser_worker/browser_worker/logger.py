"""Structured JSON-lines event logger for browser_worker diagnostics.

Each event is one JSON object per line written to a rotating log file.
The /logs endpoint tails this file so Claude can query recent events
to diagnose download failures without needing manual log inspection.
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(os.getenv("BROWSER_WORKER_LOG_FILE", "/tmp/browser_worker_events.log"))
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
_BACKUP_COUNT = 3
_MAX_TAIL = 500  # hard cap on lines returned by /logs

_handler = logging.handlers.RotatingFileHandler(
    _LOG_PATH,
    maxBytes=_MAX_BYTES,
    backupCount=_BACKUP_COUNT,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(message)s"))

_logger = logging.getLogger("browser_worker.events")
_logger.setLevel(logging.DEBUG)
_logger.addHandler(_handler)
_logger.propagate = False


def log_event(event_type: str, **fields: Any) -> None:
    """Write one JSON event line to the rotating log file."""
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
    }
    record.update(fields)
    _logger.info(json.dumps(record, default=str))


def tail_log(n: int = 100) -> list[dict[str, Any]]:
    """Return the last n events from all log files (newest last).

    Reads the current log file and up to _BACKUP_COUNT rotated files,
    merges them in chronological order, and returns the last n entries.
    """
    n = min(n, _MAX_TAIL)
    files: list[Path] = []
    # Rotated files: .log.3, .log.2, .log.1 (oldest to newest), then current
    for i in range(_BACKUP_COUNT, 0, -1):
        p = _LOG_PATH.with_suffix(f".log.{i}") if _LOG_PATH.suffix == ".log" else Path(f"{_LOG_PATH}.{i}")
        if p.exists():
            files.append(p)
    if _LOG_PATH.exists():
        files.append(_LOG_PATH)

    lines: list[str] = []
    for f in files:
        try:
            lines.extend(f.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass

    tail = lines[-n:] if len(lines) > n else lines
    events: list[dict[str, Any]] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line})
    return events
