"""Snapshot-derived signals view (NEW, P8-S5/S6).

Runs the registered LIVE models over STORED SNAPSHOT frames at the fund's
last as_of. No network, no refetch, no execution — display only."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from niveshdristi.services.vocabulary import (
    CONVICTION_CAPTION,
    lean_label,
    model_status_label,
)


def _live_bundle() -> Any:
    """The registered live model bundle (registry order, no stubs)."""
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.regime import RegimeModel
    from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
    from niveshdristi.engine.advance import ModelBundle

    return ModelBundle([TimeSeriesMomentum(), CrossSectionalMomentum(),
                        MeanReversion(), LowVolatility(), PriceRangeModel(),
                        RegimeModel(), TaEnsemble()])


def snapshot_signals(fund_id: str, base: str | Path | None = None,
                     as_of: str | None = None) -> dict[str, dict]:
    """{symbol: {lean, conviction_caption, thesis, horizon, status}} from
    the stored snapshot of `as_of` (default: the fund's last session)."""
    from niveshdristi.core.alpha import AsOfContext
    from niveshdristi.marketdata.context import build_from_full_frames
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger
    from niveshdristi.services.rules import rules_from_header

    paths = FundPaths(base).for_fund(fund_id)
    rules = rules_from_header(fund_id, base)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return {}
    as_of = as_of or records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = {}
    for symbol, digest in sorted(manifest.items()):
        matches = sorted((paths.snapshots / as_of).glob(
            f"{symbol}_{digest[:16]}.parquet"))
        if matches:
            import polars as pl

            frames[symbol] = pl.read_parquet(matches[0])
    bundle = _live_bundle()
    out: dict[str, dict] = {}
    for symbol in sorted(frames):
        entry: dict[str, Any] = {"lean": "No opinion",
                                 "conviction_caption": CONVICTION_CAPTION,
                                 "conviction": None, "thesis": "", "horizon": None,
                                 "status": ""}
        errors = 0
        models_tried = 0
        try:
            inputs = build_from_full_frames(
                as_of=date.fromisoformat(as_of), prices=frames)
            from datetime import UTC, datetime

            ctx = AsOfContext(
                as_of=datetime.combine(date.fromisoformat(as_of),
                                       datetime.min.time(), tzinfo=UTC),
                universe=(), market_id=rules.market_id,
            )
            best = None
            for model in bundle.models:
                status = model_status_label(model)
                if status:  # stub/evidence-only: labelled, never numbers
                    continue
                models_tried += 1
                try:
                    for signal in model.predict(ctx, inputs):
                        if signal.instrument.symbol == symbol:
                            best = signal
                            break
                except Exception:  # noqa: BLE001 - one model must not kill
                    errors += 1                  # the symbol's other models
            if best is not None:
                entry.update({
                    "lean": lean_label(best.conviction),
                    "conviction": best.conviction,
                    "thesis": best.thesis,
                    "horizon": best.horizon_days,
                    "status": "",
                })
            elif models_tried and errors == models_tried:
                entry["status"] = "unavailable: all models failed on this frame"
        except Exception as exc:  # noqa: BLE001 - display-only degradation
            entry["status"] = f"unavailable: {type(exc).__name__}"
        out[symbol] = entry
    return out
