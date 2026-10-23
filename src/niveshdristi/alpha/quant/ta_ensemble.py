"""TA ensemble alpha model — a PORT of the legacy signal engine.

PORTED (legacy maths, imported read-only, unchanged):
- indicators: niveshdristi.indicators.technical.compute_all_indicators
- scoring: niveshdristi.signals.engine.generate_signal_report
Both read CFG (indicator periods, signal weights) at CALL time; the equality
test pins those values explicitly.

NEW (not a port):
- AlphaModel conformance: predict(ctx, inputs) consuming validated ModelInputs.
- Mapping of the legacy SignalReport to core Signal: the legacy composite is
  a 0..1 score; conviction is derived as composite*2 - 1 (0 -> neutral,
  1 -> maximal long). This mapping is NEW code and carries no efficacy claim.
- Optional regime-aware weighting (constructor flag, default OFF = exact
  legacy weighting). When ON, NEW weights re-blend the same legacy component
  scores using REGIME_WEIGHTS below.

Thresholds/weights are named constants documented as UNVALIDATED DEFAULTS.
Thesis strings state hypotheses only, never evidence of efficacy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal
from niveshdristi.indicators.technical import compute_all_indicators  # legacy, read-only
from niveshdristi.signals.engine import generate_signal_report  # legacy, read-only

# NEW code (not ported): unvalidated defaults for the conviction mapping and
# the opt-in regime-aware weighting.
DEFAULT_HORIZON_DAYS = 10  # UNVALIDATED DEFAULT: hypothesis, not a tuned value
NEUTRAL_BAND = 0.05  # UNVALIDATED DEFAULT: |conviction| below this -> 0 (no opinion)
# UNVALIDATED DEFAULTS for the opt-in regime-aware re-weighting of the SAME
# legacy component scores (trend is emphasised in "bull", defence in "bear").
REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "bull": {"trend": 0.50, "momentum": 0.30, "volatility": 0.10, "volume": 0.10},
    "bear": {"trend": 0.20, "momentum": 0.20, "volatility": 0.35, "volume": 0.25},
    "choppy": {"trend": 0.30, "momentum": 0.30, "volatility": 0.25, "volume": 0.15},
}


class TaEnsemble:
    """TA ensemble AlphaModel wrapping the legacy indicator/signal engine."""

    def __init__(self, *, regime_aware: bool = False) -> None:
        # regime_aware=False (default) = exact legacy weighting, byte-for-byte
        # the legacy call path; True = NEW re-weighting (see module docstring).
        self._regime_aware = regime_aware

    @property
    def model_id(self) -> str:
        return "ta_ensemble"

    def legacy_report(self, symbol: str, df):
        """Direct legacy call (ported maths): indicators + signal report."""
        with_indicators = compute_all_indicators(df)
        return generate_signal_report(symbol, with_indicators)

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in inputs.prices:
            report = self.legacy_report(symbol, inputs.prices_for(symbol))
            if self._regime_aware:
                composite = self._regime_blend(symbol, report)
            else:
                composite = report.composite  # legacy value, unchanged

            conviction = composite * 2.0 - 1.0  # NEW mapping (0..1 -> -1..+1)
            if abs(conviction) < NEUTRAL_BAND:
                continue  # no opinion

            instrument = Instrument(
                symbol=symbol, exchange=ctx.market_id, market_id=ctx.market_id, currency="XXX"
            )
            signals.append(
                Signal(
                    instrument=instrument,
                    as_of=self._as_of_now(ctx),
                    conviction=round(conviction, 6),
                    horizon_days=DEFAULT_HORIZON_DAYS,
                    thesis=(
                        f"Hypothesis: trend/momentum/volatility/volume components "
                        f"scored {report.composite} on the legacy ensemble, which "
                        f"may indicate favourable conditions."
                    ),
                    evidence={
                        "legacy_composite": report.composite,
                        "trend_score": report.trend_score,
                        "momentum_score": report.momentum_score,
                        "volatility_score": report.volatility_score,
                        "volume_score": report.volume_score,
                        "regime_aware": self._regime_aware,
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def _regime_blend(self, symbol: str, report) -> float:
        """NEW (not ported): re-blend the same legacy component scores."""
        del symbol  # reserved for future per-symbol regime input
        scores = {
            "trend": report.trend_score,
            "momentum": report.momentum_score,
            "volatility": report.volatility_score,
            "volume": report.volume_score,
        }
        weights = REGIME_WEIGHTS.get("choppy", REGIME_WEIGHTS["choppy"])
        blended: float = sum(weights[k] * scores[k] for k in scores)
        return round(blended, 3)

    @staticmethod
    def _as_of_now(ctx: AsOfContext) -> datetime:
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        return stamp

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=DEFAULT_HORIZON_DAYS,
            required_data=("prices",),
            pit_safe=True,
            data_status="live",
            description="PORT of legacy TA ensemble (indicators + signal engine); "
            "conviction mapping and optional regime weighting are NEW.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = TaEnsemble()
