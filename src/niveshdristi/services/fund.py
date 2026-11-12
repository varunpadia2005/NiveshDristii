"""Paper-fund reader for the UI (NEW, P8-S1).

Composition only: reads the ledger, kill switch, chain verification and
the R9b decision sidecar; returns display-ready dicts. No execution, no
orders, no targets, no UI imports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DISCLAIMER_CACHE: str | None = None


def disclaimer_text() -> str:
    """Read the disclaimer from docs/DISCLAIMER.md (R: read the file, do
    not invent wording). First bold line of the document."""
    global _DISCLAIMER_CACHE

    if _DISCLAIMER_CACHE is not None:
        return _DISCLAIMER_CACHE
    root = Path(__file__).resolve().parents[3]
    doc = root / "docs" / "DISCLAIMER.md"
    for line in doc.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("**") and s.endswith("**"):
            _DISCLAIMER_CACHE = s.strip("*")
            break
    assert _DISCLAIMER_CACHE, "DISCLAIMER.md bold header not found"
    return _DISCLAIMER_CACHE


def read_fund(fund_id: str, base: str | Path | None = None) -> dict[str, Any]:
    """Display payload for the Paper Fund page. as_of is the last ledger
    session (the created date when empty) — NEVER the system clock."""
    from niveshdristi.paper.decisions_sidecar import read_sidecar
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.killswitch import is_halted
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    header = ledger.header()
    records = ledger.records()
    last = records[-1] if records else None
    as_of = last["session_date"] if last else header["created"]
    halted, halt_reason = is_halted(paths.root, fund_id=fund_id)
    problems = ledger.verify()

    decisions: dict[str, Any] = {"status": "decisions not recorded",
                                 "payload": None}
    if last is not None:
        from datetime import date as _date

        sidecar = read_sidecar(
            paths.root / "decisions",
            _date.fromisoformat(last["session_date"]),
            last.get("hash", ""),
        )
        if sidecar is None:
            decisions = {"status": "decisions not recorded", "payload": None}
        elif sidecar["verified"]:
            decisions = {"status": "verified", "payload": sidecar["payload"]}
        else:
            decisions = {"status": "unverified", "payload": sidecar["payload"]}

    positions = last["positions_after"] if last else []
    limitations = header.get("limitation_codes", [])
    banner = (
        "DATA LIMITATIONS: " + ", ".join(sorted(limitations))
        if limitations else None
    )
    if header.get("banner_extra"):
        banner = (
            f"{header['banner_extra']} | {banner}" if banner
            else header["banner_extra"]
        )
    from niveshdristi.markets.registry import get_registry

    market_id = header.get("market_rules_digest") and json.loads(
        header["market_rules_digest"]).get("market_id", "")
    labels = None
    if market_id:
        try:
            # importing market profile modules REGISTERS them (side effect
            # by design) — both markets' labels resolve from the header
            import niveshdristi.markets.in_us.profile  # noqa: F401
            from niveshdristi.services.labels import market_labels

            labels = market_labels(get_registry().get(market_id))
        except Exception:  # noqa: BLE001 - unknown market: no labels
            labels = None
    composition = header.get("composition", {})
    required_hist = composition.get("required_history_sessions")
    warming = (
        {"required_history": required_hist, "recorded": len(records),
         "status": "warming up" if len(records) < required_hist else "active"}
        if required_hist else None
    )
    return {
        "fund_id": fund_id,
        "as_of": as_of,  # from the DATA
        "market_labels": labels,
        "warming_up": warming,
        "banner": banner,
        "rates_banner": (
            None if header.get("rates_verified") else "RATES UNVERIFIED"
        ),
        "disclaimer": disclaimer_text(),
        "records": len(records),
        "cash": last["cash_after"] if last else None,
        "positions": positions,
        "verify": "verified" if not problems else f"FAILED: {problems[:3]}",
        "halted": halted,
        "halt_reason": halt_reason or None,
        "decisions": decisions,
    }
