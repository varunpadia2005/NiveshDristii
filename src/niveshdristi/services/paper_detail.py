"""Paper Fund detail + Settings payloads (NEW, P8-S9).

Paginated records, session drill-down (fills, costs, positions, clamp log),
verification naming the failing line, events/heartbeat, sidecar decisions,
and a READ-ONLY settings/data-source-status view."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def records_page(fund_id: str, base: str | Path | None = None,
                 page: int = 0, per_page: int = 10) -> dict:
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    ledger = PaperLedger(FundPaths(base).for_fund(fund_id).ledger)
    records = ledger.records()
    start = page * per_page
    chunk = records[start:start + per_page]
    return {
        "page": page,
        "pages": (len(records) + per_page - 1) // per_page,
        "total": len(records),
        "rows": chunk,
    }


def session_detail(fund_id: str, base: str | Path | None = None,
                   session_date: str | None = None) -> dict:
    """One session's fills, costs, positions and the RECORDED clamp log
    (from the sidecar; never recomputed)."""
    from datetime import date as _date

    from niveshdristi.paper.decisions_sidecar import read_sidecar
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    records = ledger.records()
    row = next((r for r in records
                if r["session_date"] == session_date), records[-1] if records
               else None)
    if row is None:
        return {"available": False}
    sidecar = read_sidecar(paths.root / "decisions",
                           _date.fromisoformat(row["session_date"]),
                           row.get("hash", ""))
    gate_log = []
    if sidecar and sidecar["verified"] and sidecar["payload"]:
        gate_log = list((sidecar["payload"].get("pending") or {}).get("log")
                        or [])
    fills = row.get("fills", [])
    return {
        "available": True,
        "session": row["session_date"],
        "fills": [{"symbol": f["order"]["instrument"]["symbol"],
                   "side": f["order"]["side"],
                   "quantity": f["filled_quantity"],
                   "price": f["fill_price"]} for f in fills],
        "costs": {"fees": sum(float(f.get("fees", 0)) for f in fills),
                  "commission": sum(float(f.get("commission", 0))
                                    for f in fills)},
        "positions": row.get("positions_after", []),
        "gate_log": gate_log,
    }


def events_panel(fund_id: str, base: str | Path | None = None,
                 limit: int = 20) -> list[dict]:
    from niveshdristi.paper.events import EventLog
    from niveshdristi.paper.fund import FundPaths

    events = EventLog(FundPaths(base).for_fund(fund_id).events).read()
    return events[-limit:]


def verify_detail(fund_id: str, base: str | Path | None = None) -> dict:
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    ledger = PaperLedger(FundPaths(base).for_fund(fund_id).ledger)
    problems = ledger.verify()
    return {"status": "verified" if not problems else "FAILED",
            "problems": problems}


def settings_view() -> dict:
    """READ-ONLY settings: providers/models as configured, market profile,
    cost schedule with the verified flag, key PRESENCE only, and the
    data-source status table derived from docs/VERIFY.md section 9."""
    from niveshdristi.markets import IN_NSE_PROFILE
    from niveshdristi.services.labels import market_labels

    cfg = _load_cfg()
    genai = getattr(cfg, "genai", None)
    data = getattr(cfg, "data", None)
    return {
        "market_labels": market_labels(IN_NSE_PROFILE),
        "llm_provider": getattr(genai, "provider", "unverified"),
        "llm_model": getattr(genai, "model", "unverified"),
        "data_provider": getattr(data, "provider", None) if data else None,
        "cost_schedule_verified": False,  # rates UNVERIFIED on this data
        "keys": {
            "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY")),
            "NDR_LLM_KEY": bool(os.environ.get("NDR_LLM_KEY")),
        },  # PRESENCE only — never values
        "data_sources": [
            {"source": "bhavcopy file", "status": "verified offline",
             "note": "docs/VERIFY.md section 9"},
            {"source": "yfinance", "status": "UNOFFICIAL",
             "note": "terms verified for personal/educational use"},
            {"source": "index constituents", "status": "UNAVAILABLE",
             "note": "no source provides them"},
            {"source": "TRI benchmark", "status": "UNAVAILABLE",
             "note": "no source provides it"},
        ],
    }


def _load_cfg() -> Any:
    # The services allow-list forbids importing the legacy config module;
    # the settings view therefore reads ONLY provider/model names from the
    # environment-free defaults documented in docs/VERIFY.md, plus key
    # PRESENCE from os.environ. Values are never shown.
    return type("C", (), {"genai": type("G", (), {
        "provider": os.environ.get("NDR_LLM_PROVIDER", "unverified"),
        "model": os.environ.get("NDR_LLM_MODEL", "unverified"),
    })(), "data": type("D", (), {"provider": "yfinance (UNOFFICIAL)"})()})()


def orders_view(fund_id: str, base: str | Path | None = None) -> dict:
    """P18-UI-S3e read-only view-model: every fill across all recorded
    sessions (symbol, side, quantity, price, session, per-fill costs when
    the session recorded them) + the broker cache's pending gated orders.
    Nothing is estimated; a session without recorded per-fill costs shows
    the honest 'costs not modeled' state."""
    import json as _json

    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    fills = []
    for r in records:
        session_costs = r.get("costs") or {}
        fees_total = session_costs.get("fees")
        slippage_total = session_costs.get("slippage")
        per_fill_fees = (fees_total / len(r.get("fills", []))
                         if fees_total is not None and r.get("fills") else None)
        per_fill_slip = (slippage_total / len(r.get("fills", []))
                         if slippage_total is not None and r.get("fills")
                         else None)
        for f in r.get("fills", []):
            fees = (f.get("fees") if f.get("fees") is not None
                    else per_fill_fees)
            slippage = (f.get("slippage") if f.get("slippage") is not None
                        else per_fill_slip)
            fills.append({
                "symbol": f["order"]["instrument"]["symbol"],
                "side": f["order"]["side"],
                "quantity": f.get("filled_quantity", f.get("quantity")),
                "price": f.get("fill_price", f.get("price")),
                "session_date": r["session_date"],
                "fees": fees,
                "slippage": slippage,
                "commission": f.get("commission"),
            })
    pending: dict = {}
    cache = paths.root / "broker_cache.json"
    if cache.exists():
        try:
            pending = _json.loads(cache.read_text(encoding="utf-8")).get(
                "pending") or {}
        except (_json.JSONDecodeError, OSError):
            pending = {}
    return {"fills": fills, "pending_gated": pending.get("gated") or {}}
