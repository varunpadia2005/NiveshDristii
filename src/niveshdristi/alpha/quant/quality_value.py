"""Quality/value factor model — NEW code, DATA STUB.

Scores the latest as-of-visible PIT metrics per symbol against UNVALIDATED
DEFAULT thresholds (earnings yield up = cheaper; ROCE up = higher quality)
and emits a hypothesis conviction. data_status "stub": no announcement-dated
fundamentals source exists (Phase 2 P0), so inputs are synthetic PITStore
fixtures only. Theses state hypotheses, never efficacy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS (thresholds are hypotheses, not calibrated values)
EARNINGS_YIELD_MIN = 0.05  # below this: not cheap
ROCE_MIN = 0.15  # below this: not high quality
HORIZON_DAYS = 60


class QualityValue:
    """Two-leg quality/value score over PIT records (NEW, stub)."""

    @property
    def model_id(self) -> str:
        return "quality_value"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        for symbol in inputs.fundamentals:
            metrics = {r.metric: r.value for r in inputs.fundamentals[symbol]}
            ey = metrics.get("earnings_yield")
            roce = metrics.get("roce")
            if ey is None or roce is None:
                continue
            value_leg = 1 if ey >= EARNINGS_YIELD_MIN else 0
            quality_leg = 1 if roce >= ROCE_MIN else 0
            score = (value_leg + quality_leg) / 2.0
            conviction = 2.0 * score - 1.0  # -1, 0, +1
            if conviction == 0.0:
                continue
            signals.append(
                Signal(
                    instrument=Instrument(
                        symbol=symbol,
                        exchange=ctx.market_id,
                        market_id=ctx.market_id,
                        currency="XXX",
                    ),
                    as_of=stamp,
                    conviction=round(conviction, 6),
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: {symbol} shows earnings yield {ey:.3f} and ROCE "
                        f"{roce:.3f}; the combination may indicate a quality-value "
                        f"profile."
                    ),
                    evidence={
                        "earnings_yield": round(ey, 6),
                        "roce": round(roce, 6),
                        "value_leg": value_leg,
                        "quality_leg": quality_leg,
                        "data_status": "stub",
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("fundamentals",),
            pit_safe=True,
            data_status="stub",
            description="NEW (stub): two-leg quality/value screen over PIT records; "
            "awaiting announcement-dated fundamentals.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = QualityValue()
