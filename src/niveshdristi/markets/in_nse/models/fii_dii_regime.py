"""FII/DII flow-regime model — NEW code, DATA STUB.

Market-wide aggregate flows via a neutral aux frame by ROLE:
inputs.aux["flows"] with columns (date, net_flow).

Hypothesis (no efficacy claim): sustained net inflows accompany rising
markets -> positive conviction on the universe. No live flows source exists
(Phase 2 P0: the flow sources are blocked), so data_status is "stub" —
fixture-driven only. Constants are UNVALIDATED DEFAULTS.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
FLOW_WINDOW = 20  # sessions aggregated for the regime
FLOW_SCALE = 1_000.0  # flow units (neutral) for full conviction
HORIZON_DAYS = 20


class FiiDiiRegime:
    """Aggregate-flow regime model over the 'flows' role frame."""

    @property
    def model_id(self) -> str:
        return "fii_dii_regime"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        frame = inputs.aux.get("flows")
        if not isinstance(frame, pl.DataFrame):
            return []
        if not {"date", "net_flow"}.issubset(frame.columns):
            return []
        window = frame.sort("date").tail(FLOW_WINDOW)
        if window.height < FLOW_WINDOW:
            return []
        total = sum(float(v) for v in window["net_flow"].to_list())
        conviction = max(-1.0, min(1.0, total / FLOW_SCALE))

        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        signals: list[Signal] = []
        for symbol in inputs.prices:
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
                        f"Hypothesis: aggregate net flows of {total:.1f} over the last "
                        f"{FLOW_WINDOW} sessions may accompany a supportive market."
                    ),
                    evidence={
                        "net_flow_window": round(total, 4),
                        "window": FLOW_WINDOW,
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
            required_data=("flows",),  # no live flows source yet
            pit_safe=True,
            data_status="stub",
            description="NEW (stub): aggregate flow regime over the neutral 'flows' "
            "role frame; awaiting a flows data source.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = FiiDiiRegime()
