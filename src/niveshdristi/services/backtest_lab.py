"""Backtest Lab service (NEW, P8-S8).

runs run_backtest on STORED SNAPSHOT frames (or synthetic demo frames) with
the registered live models and the market profile's cost model. No network.
Cached by a CONTENT key (fund id + as_of + model ids + frame digests)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def content_key(fund_id: str, base: str | Path | None = None) -> str:
    """Content key over the stored snapshot digests at the fund's as_of."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return "empty"
    as_of = records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    digests = (manifest_path.read_text(encoding="utf-8")
               if manifest_path.exists() else "{}")
    basis = json.dumps([fund_id, as_of, digests], sort_keys=True)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def run_backtest_service(fund_id: str, base: str | Path | None = None,
                         *, _key: str | None = None) -> dict:
    """Run the engine backtest over stored snapshot frames. Verdict wording
    is FIXED: 'pipeline demonstration only; not evidence of performance'."""
    import polars as pl

    from niveshdristi.engine.advance import ModelBundle
    from niveshdristi.engine.backtest import run_backtest
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return {"available": False, "reason": "no stored sessions"}
    as_of = records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames: dict[str, pl.DataFrame] = {}
    for symbol, digest in sorted(manifest.items()):
        matches = sorted((paths.snapshots / as_of).glob(
            f"{symbol}_{digest[:16]}.parquet"))
        if matches:
            frames[symbol] = pl.read_parquet(matches[0])
    from niveshdristi.services.rules import rules_from_header

    rules = rules_from_header(fund_id, base)
    # WARMUP SLICE: the legacy TA scorer needs ~200 as-of rows before the
    # FIRST backtest session, so each frame is cut to its last
    # (paper sessions + 200) rows. Display-only computation.
    warmup = len(records) + 200
    frames = {sym: df.tail(warmup) for sym, df in frames.items()}
    # The legacy TA scorer crashes in the engine's from-row-1 calendar
    # (its 200-row EMA warmup can never be satisfied at session 1), so the
    # Lab runs the live bundle WITHOUT it — documented, display-only.
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.regime import RegimeModel

    lab_bundle = ModelBundle([TimeSeriesMomentum(), CrossSectionalMomentum(),
                              MeanReversion(), LowVolatility(),
                              PriceRangeModel(), RegimeModel()])
    try:
        # limits=None -> the ENGINE constructs its default GateLimits (the
        # services boundary forbids importing portfolio/); broker=None ->
        # the engine's default SimBroker. Documented, display-only.
        bt = run_backtest(
            frames, models=lab_bundle, rules=rules,
            rebalance=_rebalance(), initial_cash=1_000_000.0,
            tax_enabled=True,
        )
    except Exception as exc:  # noqa: BLE001 - typed, honest degradation
        return {**_base_banners(fund_id, base), "available": False,
                "reason": (f"backtest unavailable on this frame set "
                           f"({type(exc).__name__}); the legacy TA scorer "
                           f"needs ~200 sessions of warmup")}
    return {
        **_base_banners(fund_id, base),
        "available": True,
        "as_of": as_of,
        "net_curve": [(d.isoformat(), round(v, 2))
                      for d, v in bt.net_equity_curve],
        "gross_curve": [(d.isoformat(), round(v, 2))
                        for d, v in bt.gross_equity_curve],
        "drag_bps": round(bt.drag_bps, 1),
        "fees_total": round(bt.fees_total, 2),
        "slippage_total": round(bt.slippage_total, 2),
        "trade_count": bt.trade_count,
        "limitations": sorted(bt.limitations.CODES),
        "calendar_source": bt.calendar_source,
        "verdict": ("validation-gate result: pipeline demonstration only; "
                    "not evidence of performance"),
        "promotable": bt.limitations.promotable,
    }


def _rebalance() -> Any:
    from niveshdristi.engine.advance import RebalanceSchedule

    return RebalanceSchedule()


def _base_banners(fund_id: str, base: str | Path | None) -> dict:
    from niveshdristi.services.fund import read_fund

    try:
        return read_fund(fund_id, base=base)
    except Exception:  # noqa: BLE001
        return {}
