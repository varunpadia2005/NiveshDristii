"""Snapshot retention (NEW, P10-S6 / D7).

`prune_snapshots` deletes ONLY per-session snapshot directories (parquet
+ manifest) older than the last `keep_last` sessions. NEVER touches the
ledger, the header, the decision sidecars, the broker cache, halt or
heartbeat files. Dry-run is the default; --apply (CLI) is required to
actually delete. Replay of pruned sessions reports "snapshots unavailable"
explicitly (never a silent pass)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from niveshdristi.paper.fund import FundPaths
from niveshdristi.paper.ledger import PaperLedger


def prune_snapshots(fund_id: str, base: str | Path | None = None, *,
                    keep_last: int = 60, apply: bool = False) -> dict[str, Any]:
    """Plan (dry-run) or execute the snapshot prune. Returns the plan."""
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1")
    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    records = ledger.records()
    sessions = [r["session_date"] for r in records]
    keep = set(sessions[-keep_last:])
    doomed: list[str] = []
    if paths.snapshots.exists():
        for d in sorted(paths.snapshots.iterdir()):
            if d.is_dir() and d.name not in keep:
                doomed.append(d.name)
    result: dict[str, Any] = {
        "fund_id": fund_id,
        "keep_last": keep_last,
        "kept": sorted(keep),
        "prunable": sorted(doomed),
        "applied": apply,
    }
    if apply:
        import shutil

        for name in doomed:
            shutil.rmtree(paths.snapshots / name)
    return result
