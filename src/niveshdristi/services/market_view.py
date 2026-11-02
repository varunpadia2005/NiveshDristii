"""Market Overview + Signals Board computations (NEW, P8-S6).

Only what is derivable from STORED SNAPSHOTS. Regime/benchmark/VIX/sector/
flows are honestly unavailable (the regime model needs aux frames the
snapshots do not carry). No network."""

from __future__ import annotations

import json
from pathlib import Path

from niveshdristi.services.vocabulary import lean_label


def market_overview(fund_id: str, base: str | Path | None = None) -> dict:
    """Overview payload: last-data-session badge (never Open/Closed — the
    official holiday calendar is NOT loaded) + honest unavailable list."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger
    from niveshdristi.services.fund import read_fund

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    last_session = records[-1]["session_date"] if records else None
    base_payload = read_fund(fund_id, base=base)
    return {
        **base_payload,
        "as_of": last_session,
        "last_data_session": last_session,
        "holiday_note": ("official holiday calendar is not loaded; sessions "
                         "are data-derived"),
        "unavailable": ["benchmark", "Bank Nifty", "India VIX",
                        "sector heatmap", "FII/DII flows", "regime state "
                        "(needs aux frames not in snapshots)"],
    }


def signals_board(fund_id: str, base: str | Path | None = None,
                  min_conviction: float | None = None) -> list[dict]:
    """Rows for the board: every STORED instrument at the fund's last
    as_of — lean, conviction (uncalibrated), horizon, thesis, data_status,
    liquidity (last-session volume from the snapshot)."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger
    from niveshdristi.services.signals_view import snapshot_signals

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return []
    as_of = records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    volumes: dict[str, int] = {}
    if manifest_path.exists():
        import polars as pl

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for symbol, digest in sorted(manifest.items()):
            matches = sorted((paths.snapshots / as_of).glob(
                f"{symbol}_{digest[:16]}.parquet"))
            if matches:
                volumes[symbol] = int(pl.read_parquet(matches[0])["volume"][-1])
    signals = snapshot_signals(fund_id, base=base, as_of=as_of)
    rows = []
    for symbol in sorted(volumes):
        entry = signals.get(symbol, {})
        conviction = entry.get("conviction")
        if min_conviction is not None and (
                conviction is None or abs(conviction) < min_conviction):
            continue
        rows.append({
            "symbol": symbol,
            "lean": lean_label(conviction),
            "conviction": conviction,
            "conviction_caption": entry.get("conviction_caption", ""),
            "horizon": entry.get("horizon"),
            "thesis": entry.get("thesis", ""),
            "data_status": entry.get("status") or "live",
            "last_volume": volumes[symbol],
        })
    return rows
