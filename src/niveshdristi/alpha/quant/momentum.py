"""Momentum models — NEW code (no legacy maths involved).

Two models:
- TimeSeriesMomentum: each symbol's own trailing return, skip-adjusted.
- CrossSectionalMomentum: conviction from the symbol's RANK of that same
  trailing return across the universe in inputs.

All parameters are UNVALIDATED DEFAULTS (hypotheses, not tuned values);
theses state hypotheses only, never efficacy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
LOOKBACK_DAYS = 120  # trailing-return window (before the skip period)
SKIP_DAYS = 5  # most recent days skipped (avoid short-reversal noise)
HORIZON_DAYS = 20  # documented signal horizon


def trailing_return(closes: list[float]) -> float | None:
    """Skip-adjusted trailing return: close[end]/close[start] - 1 where
    end = last - SKIP_DAYS and start = end - LOOKBACK_DAYS."""
    end = len(closes) - 1 - SKIP_DAYS
    start = end - LOOKBACK_DAYS
    if start < 0 or closes[start] == 0:
        return None
    return float(closes[end]) / float(closes[start]) - 1.0


def _stamp(ctx: AsOfContext) -> datetime:
    stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
    return stamp


def _instrument(ctx: AsOfContext, symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol, exchange=ctx.market_id, market_id=ctx.market_id, currency="XXX"
    )


class TimeSeriesMomentum:
    """Per-symbol trailing-return momentum (NEW)."""

    @property
    def model_id(self) -> str:
        return "momentum_ts"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in inputs.prices:
            closes = inputs.prices_for(symbol)["close"].to_list()
            ret = trailing_return(closes)
            if ret is None:
                continue
            conviction = max(-1.0, min(1.0, ret))  # UNVALIDATED DEFAULT: clip raw return
            if conviction == 0.0:
                continue
            signals.append(
                Signal(
                    instrument=_instrument(ctx, symbol),
                    as_of=_stamp(ctx),
                    conviction=round(conviction, 6),
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: {symbol}'s trailing {LOOKBACK_DAYS}-day return "
                        f"(skipping {SKIP_DAYS}d) was {ret:.4f}, which may persist."
                    ),
                    evidence={
                        "trailing_return": round(ret, 6),
                        "lookback": LOOKBACK_DAYS,
                        "skip": SKIP_DAYS,
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),
            pit_safe=True,
            data_status="live",
            description="NEW: time-series momentum (trailing return, skip-adjusted).",
        )


class CrossSectionalMomentum:
    """Rank-based momentum across the symbols in inputs (NEW)."""

    @property
    def model_id(self) -> str:
        return "momentum_cs"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        rets: dict[str, float] = {}
        for symbol in inputs.prices:
            closes = inputs.prices_for(symbol)["close"].to_list()
            ret = trailing_return(closes)
            if ret is not None:
                rets[symbol] = ret
        if len(rets) < 2:
            return []  # cross-sectional ranking needs several instruments

        ordered = sorted(rets, key=lambda s: rets[s])  # ascending return
        k = len(ordered)
        signals: list[Signal] = []
        for rank, symbol in enumerate(ordered):
            conviction = 2.0 * (rank / (k - 1)) - 1.0  # lowest -> -1, highest -> +1
            signals.append(
                Signal(
                    instrument=_instrument(ctx, symbol),
                    as_of=_stamp(ctx),
                    conviction=round(conviction, 6),
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: {symbol} ranks {rank + 1}/{k} by trailing "
                        f"{LOOKBACK_DAYS}-day return, which may persist relative to peers."
                    ),
                    evidence={
                        "trailing_return": round(rets[symbol], 6),
                        "rank": rank + 1,
                        "universe_size": k,
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),
            pit_safe=True,
            data_status="live",
            description="NEW: cross-sectional momentum (rank of trailing return).",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = TimeSeriesMomentum()
__: AlphaModel = CrossSectionalMomentum()
