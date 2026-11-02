"""Fund Overview computations (NEW, P8-S5).

All numbers derive from the LEDGER + STORED SNAPSHOTS + EVENTS with
hand-computed tests on a synthetic fund. No execution, no targets, no UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from niveshdristi.services.format import format_money
from niveshdristi.services.vocabulary import lean_label


def _last_snap_close(paths: Any, as_of: str, symbol: str) -> float | None:
    snap_dir = paths.snapshots / as_of
    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = manifest.get(symbol)
    if not digest:
        return None
    import polars as pl

    matches = sorted(snap_dir.glob(f"{symbol}_{digest[:16]}.parquet"))
    if not matches:
        return None
    frame = pl.read_parquet(matches[0])
    return float(frame["close"][-1])


def fund_overview(fund_id: str, base: str | Path | None = None) -> dict:
    """Overview payload: KPI ribbon, health chips, positions with display
    indicators, last-session change feed and the needs-attention list."""
    from niveshdristi.markets import IN_NSE_PROFILE
    from niveshdristi.paper.events import EventLog
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger
    from niveshdristi.services.fund import read_fund

    paths = FundPaths(base).for_fund(fund_id)
    base_payload = read_fund(fund_id, base=base)
    ledger = PaperLedger(paths.ledger)
    records = ledger.records()
    if not records:
        return {**base_payload, "kpis": None, "positions_view": [],
                "change_feed": [], "needs_attention": ["no sessions yet"]}
    last, prev = records[-1], (records[-2] if len(records) > 1 else None)

    # KPI ribbon (hand-derived formulas, tested)
    equity = float(last["equity_after"])
    net_pnl = (equity - float(prev["equity_after"])) if prev else 0.0
    gross_now = float(last["risk_metrics"]["gross_equity_after"])
    gross_prev = (float(prev["risk_metrics"]["gross_equity_after"])
                  if prev else gross_now)
    gross_pnl = gross_now - gross_prev

    positions_view = []
    for pos in last["positions_after"]:
        symbol = pos["instrument"]["symbol"]
        close = _last_snap_close(paths, last["session_date"], symbol)
        avg = float(pos["avg_cost"])
        unrealised = ((close - avg) / avg if (close and avg) else None)
        positions_view.append({
            "symbol": symbol,
            "quantity": pos["shares"],
            "avg_cost": avg,
            "last_close": close,
            "unrealised_pct": unrealised,
        })

    events = EventLog(paths.events).read()
    change_feed = [e for e in events
                   if e.get("event") in ("tick", "quality", "halt",
                                         "resume", "recover")
                   and str(e.get("fund_id")) == fund_id][-8:]

    needs: list[str] = []
    if base_payload["verify"] != "verified":
        needs.append(f"ledger verification: {base_payload['verify']}")
    if base_payload["halted"]:
        needs.append(f"fund is halted: {base_payload['halt_reason']}")
    if base_payload["decisions"]["status"] == "unverified":
        needs.append("decision sidecar UNVERIFIED (hash mismatch)")
    limitations = header_limitations(base_payload)
    needs.append(f"{len(limitations)} active data limitation(s)")

    return {
        **base_payload,
        "kpis": {
            "fund_value": format_money(equity, IN_NSE_PROFILE),
            "net_pnl_session": format_money(net_pnl, IN_NSE_PROFILE),
            "gross_pnl_session": format_money(gross_pnl, IN_NSE_PROFILE),
            "net_pnl_value": net_pnl,
        },
        "positions_view": positions_view,
        "change_feed": [
            {"event": e.get("event"),
             "detail": json.dumps({k: v for k, v in e.items()
                                   if k not in ("event", "timestamp")},
                                  sort_keys=True, default=str)[:160]}
            for e in change_feed
        ],
        "needs_attention": needs,
    }


def header_limitations(payload: dict) -> list[str]:
    banner = payload.get("banner") or ""
    prefix = "DATA LIMITATIONS: "
    return banner[len(prefix):].split(", ") if banner.startswith(prefix) else []


def lean_for_position(symbol: str, signals: dict[str, dict]) -> str:
    """Icon+word lean for a position row (from the snapshot signals view)."""
    entry = signals.get(symbol)
    return lean_label(entry["conviction"]) if entry else "No opinion"
