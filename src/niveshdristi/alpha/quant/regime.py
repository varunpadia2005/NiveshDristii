"""Regime model — NEW code (simple trend/vol states).

The model receives frames BY ROLE, never by symbol literal: the benchmark
frame arrives as inputs.aux["benchmark"] (a price frame with a close column)
and the volatility series as inputs.aux["volatility"] (a frame with a value
column). Which actual symbols fill those roles is decided per market by the
market profile (benchmark_symbol / volatility_index_symbol) at a composition
point — never inside this module.

Signals are EVIDENCE-ONLY (conviction exactly 0.0): the regime state is
context for other models, not a directional view. Aux frames are truncated
to as_of defensively inside this module — REDUNDANT second layer: the
builder (marketdata.context) validates and truncates aux frames by ROLE
since G2a; this self-truncation remains as belt-and-braces.
UNVALIDATED DEFAULTS throughout; theses state hypotheses only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
TREND_WINDOW = 60  # benchmark return window
TREND_THRESHOLD = 0.10  # |return| beyond this = directional trend
VIX_HIGH = 25.0  # volatility-index level considered high
HORIZON_DAYS = 5  # evidence freshness


def classify_regime(benchmark_closes: list[float], volatility_last: float) -> str:
    """Simple trend/vol state: 'bull' | 'bear' | 'choppy'."""
    window = benchmark_closes[-(TREND_WINDOW + 1):]
    if len(window) < TREND_WINDOW + 1:
        return "insufficient_data"
    ret = float(window[-1]) / float(window[0]) - 1.0
    if (ret > TREND_THRESHOLD) and (volatility_last < VIX_HIGH):
        return "bull"
    if (ret < -TREND_THRESHOLD) or (volatility_last >= VIX_HIGH):
        return "bear"
    return "choppy"


def _truncate_aux(frame: pl.DataFrame, as_of: date) -> pl.DataFrame:
    cutoff = as_of.isoformat()
    if "date" not in frame.columns:
        return frame
    return frame.filter(pl.col("date").cast(pl.String).str.slice(0, 10) <= cutoff)


class RegimeModel:
    """Evidence-only trend/vol regime classifier (NEW)."""

    @property
    def model_id(self) -> str:
        return "regime"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        benchmark = inputs.aux.get("benchmark")
        volatility = inputs.aux.get("volatility")
        if not isinstance(benchmark, pl.DataFrame) or not isinstance(volatility, pl.DataFrame):
            return []  # roles not supplied: no opinion

        bench_trunc = _truncate_aux(benchmark, inputs.as_of)
        vol_trunc = _truncate_aux(volatility, inputs.as_of)
        if bench_trunc.height == 0 or vol_trunc.height == 0:
            return []
        closes = bench_trunc["close"].to_list()
        vol_last = float(vol_trunc["value"].to_list()[-1])
        state = classify_regime(closes, vol_last)

        signals: list[Signal] = []
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        for symbol in inputs.prices:
            signals.append(
                Signal(
                    instrument=Instrument(
                        symbol=symbol,
                        exchange=ctx.market_id,
                        market_id=ctx.market_id,
                        currency="XXX",
                    ),
                    as_of=stamp,
                    conviction=0.0,  # evidence-only: regime is context, not a view
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"EVIDENCE-ONLY (no directional view): market regime state "
                        f"is '{state}' (volatility index at {vol_last:.2f})."
                    ),
                    evidence={
                        "regime_state": state,
                        "volatility_last": round(vol_last, 4),
                        "trend_window": TREND_WINDOW,
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),  # via role frames (benchmark, volatility)
            pit_safe=True,
            data_status="live",  # computed purely from supplied frames
            description="NEW: evidence-only trend/vol regime state from "
            "ROLE-based benchmark and volatility frames.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = RegimeModel()
