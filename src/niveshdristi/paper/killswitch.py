"""Kill switch (NEW, Phase 6, amendment F).

A halt flag file (JSON: fund id, reason, session, event id) in the fund
directory. Semantics:
- any exception inside a tick halts the fund (the tick driver writes the
  flag via halt());
- `halt` writes the flag; `resume` REMOVES it (requires a note, logged);
- a halted fund's tick is a logged no-op;
- an unreadable, corrupt or mismatched flag file is treated as HALTED
  (fail-safe) with a loud error.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from niveshdristi.core.errors import KillSwitchError


class KillSwitchResumeError(KillSwitchError):
    """resume called when the fund is not halted, or without a note."""



def halt(
    fund_dir: Path,
    *,
    fund_id: str,
    reason: str,
    session: date,
    event_id: str,
) -> dict:
    """Write the halt flag; returns the flag payload (also logged by the caller)."""
    payload = {
        "fund_id": fund_id,
        "reason": reason,
        "session": session.isoformat(),
        "event_id": event_id,
    }
    fund_dir.mkdir(parents=True, exist_ok=True)
    (fund_dir / "halt.flag").write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8"
    )
    return payload


def resume(fund_dir: Path, *, note: str) -> None:
    """Remove the halt flag; requires a non-empty note (logged by caller)."""
    if not note or not note.strip():
        raise KillSwitchResumeError("resume requires a non-empty note")
    flag = fund_dir / "halt.flag"
    if not flag.exists():
        raise KillSwitchResumeError("fund is not halted")
    flag.unlink()


def is_halted(fund_dir: Path, *, fund_id: str) -> tuple[bool, str]:
    """Fail-safe halted check: (halted, reason).

    An unreadable, corrupt or MISMATCHED flag file is treated as HALTED
    with a loud error message in the reason (fail-safe per amendment F).
    """
    flag = fund_dir / "halt.flag"
    if not flag.exists():
        return False, ""
    try:
        data = json.loads(flag.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return True, (
                "UNREADABLE halt flag (fail-safe halted): flag is not a "
                "JSON object"
            )
        if data.get("fund_id") != fund_id:
            return True, (
                f"halt flag MISMATCH: fund_id {data.get('fund_id')!r} != "
                f"{fund_id!r} (fail-safe: treated as halted)"
            )
        return True, str(data.get("reason", ""))
    except (json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
        return True, f"UNREADABLE halt flag (fail-safe halted): {exc}"
