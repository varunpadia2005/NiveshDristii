"""Price-range evidence model — FRESH code (no legacy implementation exists).

This is NOT a port: no legacy price-range engine exists (the legacy tree has
only a PriceRange dataclass placeholder, per docs/AUDIT.md conflict #5).

Everything here is NEW: support/resistance from the recent window and
ATR-based entry/stop zones, emitted ONLY as evidence for other models.
If a Signal is produced, its conviction is EXACTLY 0.0 and the thesis states
evidence-only — this model never expresses directional opinion.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS (hypotheses, not tuned values)
LOOKBACK_DAYS = 20  # window for support/resistance
ATR_PERIOD = 14  # true-range averaging window
STOP_ATR_MULT = 2.0  # stop zone: close - STOP_ATR_MULT * ATR
ENTRY_ATR_FRACTION = 0.5  # entry zone half-width: ENTRY_ATR_FRACTION * ATR
DEFAULT_HORIZON_DAYS = 5  # evidence freshness horizon


def compute_price_evidence(df: pl.DataFrame) -> dict[str, float | int | str]:
    """Support/resistance + ATR-based zones from a price frame.

    Frame needs date, high, low, close columns. Returns floats keyed for
    direct inclusion in Signal.evidence.
    """
    closes = df["close"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    close = float(closes[-1])
    high = float(max(highs[-LOOKBACK_DAYS:]))
    low = float(min(lows[-LOOKBACK_DAYS:]))

    # True range per bar (first bar: high-low only, no previous close)
    trs = [float(highs[i]) - float(lows[i]) for i in range(len(closes))]
    for i in range(1, len(closes)):
        trs[i] = max(
            float(highs[i]) - float(lows[i]),
            abs(float(highs[i]) - float(closes[i - 1])),
            abs(float(lows[i]) - float(closes[i - 1])),
        )
    atr = sum(trs[-ATR_PERIOD:]) / ATR_PERIOD

    return {
        "support": low,
        "resistance": high,
        "atr": round(atr, 6),
        "entry_zone_low": round(close - ENTRY_ATR_FRACTION * atr, 6),
        "entry_zone_high": round(close + ENTRY_ATR_FRACTION * atr, 6),
        "stop_zone": round(close - STOP_ATR_MULT * atr, 6),
    }


class PriceRangeModel:
    """Evidence-only AlphaModel: conviction is always exactly 0.0."""

    @property
    def model_id(self) -> str:
        return "price_range"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in inputs.prices:
            evidence = compute_price_evidence(inputs.prices_for(symbol))
            instrument = Instrument(
                symbol=symbol, exchange=ctx.market_id, market_id=ctx.market_id, currency="XXX"
            )
            signals.append(
                Signal(
                    instrument=instrument,
                    as_of=self._stamp(ctx),
                    conviction=0.0,  # evidence-only: never a directional opinion
                    horizon_days=DEFAULT_HORIZON_DAYS,
                    thesis=(
                        f"EVIDENCE-ONLY (no directional view): support/resistance "
                        f"and ATR entry/stop zones for {symbol}."
                    ),
                    evidence=evidence,
                    model_id=self.model_id,
                )
            )
        return signals

    @staticmethod
    def _stamp(ctx: AsOfContext) -> datetime:
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        return stamp

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=DEFAULT_HORIZON_DAYS,
            required_data=("prices",),
            pit_safe=True,
            data_status="live",  # computed purely from price frames
            description="NEW (not a port): evidence-only support/resistance and "
            "ATR entry/stop zones; conviction always 0.0.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = PriceRangeModel()
