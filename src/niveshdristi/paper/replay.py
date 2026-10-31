"""Paper replay (NEW, Phase 6) — the C5 done-when.

Re-runs advance() from the STORED per-session snapshots (never a refetch:
yfinance restates adjusted history after corporate actions) and compares
every regenerated record's hash with the ledger's stored hash. Byte-for-
byte equality holds because the money state is paise-snapped (amendment A)
and the record stamps are session-derived (deterministic).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from niveshdristi.core.market_rules import MarketRules
from niveshdristi.engine.advance import (
    FundState,
    ModelBundle,
    RebalanceSchedule,
    advance,
)
from niveshdristi.execution.sim_broker import SimBroker
from niveshdristi.paper.fund import FundPaths
from niveshdristi.paper.ledger import PaperLedger


def replay_fund(
    fund_id: str,
    *,
    base: str | Path | None = None,
    models: ModelBundle,
    limits: Any,
    rebalance: RebalanceSchedule,
) -> dict:
    """Replay the ledger sessions from stored snapshots; compare hashes."""
    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    header = ledger.header()
    records = ledger.records()
    if not records:
        return {"byte_identical": True, "sessions": [], "note": "no records to replay"}

    rules = MarketRules.model_validate(json.loads(header["market_rules_digest"]))
    initial_cash = float(header.get("initial_cash_paise", 0)) / 100.0
    broker = SimBroker(rates=rules.rates, price_limits=rules.price_limits)
    fund = FundState(cash=initial_cash)
    comparisons: list[dict] = []
    byte_identical = True

    for stored in records:
        session = date.fromisoformat(stored["session_date"])
        snapshot_dir = paths.snapshots / session.isoformat()
        manifest_path = snapshot_dir / "manifest.json"
        if not manifest_path.exists():
            comparisons.append({
                "session": session.isoformat(),
                "match": None,
                "note": "no stored snapshot (tick predates snapshots)",
            })
            byte_identical = False
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frames: dict[str, pl.DataFrame] = {}
        missing = False
        for symbol, digest in sorted(manifest.items()):
            matches = sorted(snapshot_dir.glob(f"{symbol}_{digest[:16]}.parquet"))
            if not matches:
                comparisons.append({
                    "session": session.isoformat(), "match": False,
                    "note": f"missing snapshot for {symbol}",
                })
                missing = True
                byte_identical = False
                break
            frames[symbol] = pl.read_parquet(matches[0])
        if missing:
            continue

        fund, record = advance(
            fund, session, broker, frames,
            models=models, rules=rules, limits=limits,
            rebalance=rebalance, tax_enabled=False,
        )
        regenerated_hash = record.compute_hash()
        stored_hash = stored.get("hash", "")
        matches = regenerated_hash == stored_hash
        byte_identical = byte_identical and matches
        comparisons.append({
            "session": session.isoformat(),
            "match": matches,
        })
        if not matches:
            comparisons[-1]["regenerated_hash"] = regenerated_hash
            comparisons[-1]["stored_hash"] = stored_hash

    return {
        "byte_identical": byte_identical,
        "sessions": comparisons,
    }
