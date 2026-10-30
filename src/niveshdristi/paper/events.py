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
    """Append-only events.jsonl (one JSON object per line)."""

    def __init__(
        self, path: Path, *, clock: Clock = utc_clock
    ) -> None:
        self.path = Path(path)
        self._clock = clock

    def append(self, event_type: str, **fields: Any) -> dict:
        """Append one event; wall-clock timestamp from the INJECTED clock."""
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
