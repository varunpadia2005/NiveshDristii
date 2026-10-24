"""Mean-reversion model — NEW code.

Conviction is CONTRARIAN: a z-score of the latest close above its rolling
mean produces a negative (bearish) conviction, below produces positive.
All parameters are UNVALIDATED DEFAULTS; theses state hypotheses only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
Z_WINDOW = 20  # rolling window for mean/std
Z_CAP = 3.0  # |z| beyond this clips to full conviction
HORIZON_DAYS = 10


def zscore_last(closes: list[float]) -> float | None:
    """z-score of the last close vs the Z_WINDOW population mean/std."""
    window = closes[-Z_WINDOW:]
    if len(window) < Z_WINDOW:
        return None
    mean = sum(window) / Z_WINDOW
    var = sum((c - mean) ** 2 for c in window) / Z_WINDOW
    if var == 0:
        return None  # degenerate series: no reversion signal
    z: float = (window[-1] - mean) / (var ** 0.5)
    return z


class MeanReversion:
    """Contrarian z-score model (NEW)."""

    @property
    def model_id(self) -> str:
        return "mean_reversion"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in inputs.prices:
            closes = inputs.prices_for(symbol)["close"].to_list()
            z = zscore_last(closes)
            if z is None:
                continue
            scaled = max(-1.0, min(1.0, -z / Z_CAP))  # contrarian, clipped
            if scaled == 0.0:
                continue
            signals.append(
                Signal(
                    instrument=Instrument(
                        symbol=symbol,
                        exchange=ctx.market_id,
                        market_id=ctx.market_id,
                        currency="XXX",
                    ),
                    as_of=self._stamp(ctx),
                    conviction=round(scaled, 6),
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: {symbol}'s last close is {z:.2f} std devs from "
                        f"its {Z_WINDOW}-day mean and may revert toward it."
                    ),
                    evidence={"z_score": round(z, 6), "window": Z_WINDOW},
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
            description="NEW: contrarian mean reversion on rolling z-score.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = MeanReversion()
