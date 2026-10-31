"""Low-volatility model — NEW code.

Conviction is proportional to how much a symbol's realized volatility is
BELOW the cross-sectional median of the symbols in inputs (defensive,
low-vol tilt). Symbols at or above the median get no opinion.
UNVALIDATED DEFAULTS throughout; theses state hypotheses only.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
VOL_WINDOW = 60  # daily-return window for realized volatility
HORIZON_DAYS = 60


def realized_vol(closes: list[float]) -> float | None:
    """Population std of daily returns over the last VOL_WINDOW closes."""
    window = closes[-(VOL_WINDOW + 1):]
    if len(window) < VOL_WINDOW + 1:
        return None
    rets = [
        (float(window[i]) / float(window[i - 1])) - 1.0 for i in range(1, len(window))
    ]
    return statistics.pstdev(rets)


class LowVolatility:
    """Below-median-volatility tilt (NEW)."""

    @property
    def model_id(self) -> str:
        return "low_volatility"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        vols: dict[str, float] = {}
        for symbol in inputs.prices:
            vol = realized_vol(inputs.prices_for(symbol)["close"].to_list())
            if vol is not None:
                vols[symbol] = vol
        if len(vols) < 2:
            return []  # cross-sectional median needs several instruments
        median = statistics.median(vols.values())

        signals: list[Signal] = []
        for symbol, vol in sorted(vols.items()):
            if vol >= median or median == 0:
                continue  # no opinion at/above median volatility
            conviction = (median - vol) / median  # in (0, 1) by construction
            signals.append(
                Signal(
                    instrument=Instrument(
                        symbol=symbol,
                        exchange=ctx.market_id,
                        market_id=ctx.market_id,
                        currency="XXX",
                    ),
                    as_of=self._stamp(ctx),
                    conviction=round(conviction, 6),
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: {symbol}'s realized volatility ({vol:.4f}) is below "
                        f"the universe median ({median:.4f}), a defensive profile that "
                        f"may carry lower drawdowns."
                    ),
                    evidence={"realized_vol": round(vol, 6), "median_vol": round(median, 6)},
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
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),
            pit_safe=True,
            data_status="live",
            description="NEW: below-median realized volatility tilt.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = LowVolatility()
