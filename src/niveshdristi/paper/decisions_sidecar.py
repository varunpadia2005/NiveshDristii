"""Per-session decision sidecars (NEW, R9b decision).

OUTSIDE the hash chain: the ledger is truth; a sidecar is a convenience
artifact for the Paper Fund page (targets, gate log, pending weights that
the record itself does not serialize). Written AFTER the ledger commit
(same commit order as snapshots). Verification is content-based: the
filename carries sha256 of the payload; a tampered sidecar is "unverified"
and NEVER trusted for display beyond an explicit "unverified" label.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1


def _digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def write_sidecar(
    directory: Path, session: date, record_hash: str, payload: dict
) -> Path:
    """Content-hashed sidecar: decisions/<session>_<payload-sha16>.json."""
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "format_version": FORMAT_VERSION,
        "record_hash": record_hash,
        "payload": payload,
    }
    digest = _digest(body)
    path = directory / f"{session.isoformat()}_{digest[:16]}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, sort_keys=True, default=str),
                   encoding="utf-8")
    tmp.replace(path)
    return path


def read_sidecar(
    directory: Path, session: date, record_hash: str
) -> dict[str, Any] | None:
    """Return {"verified": bool, "payload": {...}} or None when absent.

    verified=True requires the payload's record_hash to match the ledger's
    AND the file content digest to match its own filename. Anything else is
    "unverified" (display-only) or None (fallback to the ledger record)."""
    if not directory.exists():
        return None
    for path in sorted(directory.glob(f"{session.isoformat()}_*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {"verified": False, "payload": None}
        digest = _digest(body)
        if not digest.startswith(path.stem.rsplit("_", 1)[-1]):
            return {"verified": False, "payload": None}
        if body.get("record_hash") != record_hash:
            return {"verified": False, "payload": body.get("payload")}
        return {"verified": True, "payload": body.get("payload")}
    return None
