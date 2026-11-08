"""Events log and heartbeat (NEW, Phase 6, amendment G).

events.jsonl: append-only, one JSON object per line, for every tick,
no-op, failure, halt, resume, recover, unlock. Wall-clock timestamps are
allowed ONLY here and in the heartbeat — via an INJECTED aware-UTC clock —
never in ledger records or hashes.

Heartbeat: updated on every tick including no-ops.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

# Injected clock type: returns an aware UTC datetime
Clock = Callable[[], datetime]


def utc_clock() -> datetime:
    """The default injected clock (aware UTC)."""
    from datetime import UTC

    return datetime.now(UTC)


class EventLog:
    """Append-only events.jsonl (one JSON object per line).

    Rotation (P10-S6 / D7): when the file exceeds rotation_threshold_bytes
    (injectable, UNVALIDATED DEFAULT 5 MB), it is renamed to
    events.jsonl.1 — keeping exactly ONE rotated generation — before the
    new event is appended."""

    def __init__(
        self, path: Path, *, clock: Clock = utc_clock,
        rotation_threshold_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self.path = Path(path)
        self._clock = clock
        self._rotation_threshold = rotation_threshold_bytes

    def _rotate_if_needed(self) -> None:
        if (not self.path.exists()
                or self.path.stat().st_size < self._rotation_threshold):
            return
        self.path.replace(self.path.with_name(self.path.name + ".1"))

    def append(self, event_type: str, **fields: Any) -> dict:
        """Append one event; wall-clock timestamp from the INJECTED clock."""
        self._rotate_if_needed()
        payload = {
            "event": event_type,
            "timestamp": self._clock().isoformat(),
            **fields,
        }
        line = json.dumps(payload, sort_keys=True, default=str)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "ab") as handle:
            handle.write((line + "\n").encode("utf-8"))
            handle.flush()
            import os

            os.fsync(handle.fileno())
        return payload

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


def write_heartbeat(path: Path, *, clock: Clock = utc_clock, **fields: Any) -> None:
    """Heartbeat file updated on every tick INCLUDING no-ops."""
    payload = {"timestamp": clock().isoformat(), **fields}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
