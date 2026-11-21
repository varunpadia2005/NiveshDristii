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
        "unavailable": ["benchmark index", "bank index", "volatility index",
                        "sector heatmap", "institutional flows", "regime "
                        "state (needs aux frames not in snapshots)"],
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


def watchlist(fund_id: str, base: str | Path | None = None) -> dict:
    """P18-UI-S3b read-only view-model: the fund's declared universe plus
    every symbol with stored snapshot data, each with last close /
    previous close / change when snapshots exist — never invented.

    Returns {market_labels-ish? no: as_of, currency_code, rows: [
      {symbol, has_data, last_close, prev_close, change}]}
    """
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    header = ledger.header()
    records = ledger.records()
    as_of = records[-1]["session_date"] if records else None

    symbols: list[str] = list(header.get("universe") or [])
    manifest: dict = {}
    if as_of:
        manifest_path = paths.snapshots / as_of / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for s in manifest:
                if s not in symbols:
                    symbols.append(s)

    rows = []
    for s in sorted(symbols):
        last_close = prev_close = None
        if as_of and s in manifest:
            import polars as pl

            digest = manifest[s]
            matches = sorted((paths.snapshots / as_of).glob(
                f"{s}_{digest[:16]}.parquet"))
            if matches:
                frame = pl.read_parquet(matches[0])
                last_close = float(frame["close"][-1])
                prev_close = (float(frame["close"][-2])
                              if len(frame) >= 2 else None)
        change = (last_close - prev_close
                  if last_close is not None and prev_close is not None
                  else None)
        rows.append({"symbol": s, "has_data": last_close is not None,
                     "last_close": last_close, "prev_close": prev_close,
                     "change": change})
    return {"as_of": as_of, "rows": rows}
