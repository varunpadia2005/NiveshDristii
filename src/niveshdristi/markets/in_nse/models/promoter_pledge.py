"""Promoter pledge-trend model — NEW code, DATA STUB.

India-specific but literal-free: consumes a neutral aux frame by ROLE,
inputs.aux["promoter_pledge"] with columns (symbol, date, pledge_pct).

Hypothesis (no efficacy claim): a RISING promoter pledge percentage is a
red flag -> negative conviction. No real source for pledge history exists
yet (Phase 2 P0: filings sources blocked), so data_status is "stub" — the
maths is fixture-driven only. Constants are UNVALIDATED DEFAULTS.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
TREND_WINDOW = 4  # trailing pledges for the trend
HORIZON_DAYS = 60


class PromoterPledge:
    """Pledge-trend red-flag model over the 'promoter_pledge' role frame."""

    @property
    def model_id(self) -> str:
        return "promoter_pledge"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        frame = inputs.aux.get("promoter_pledge")
        if not isinstance(frame, pl.DataFrame):
            return []
        if not {"symbol", "date", "pledge_pct"}.issubset(frame.columns):
            return []

        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        signals: list[Signal] = []
        for symbol in inputs.prices:
            rows = frame.filter(pl.col("symbol") == symbol).sort("date")
            pledges = [float(v) for v in rows["pledge_pct"].to_list() if v is not None]
            window = pledges[-TREND_WINDOW:]
            if len(window) < TREND_WINDOW:
                continue
            delta = window[-1] - window[0]  # rising pledge = red flag
            conviction = max(-1.0, min(1.0, -delta / 5.0))  # 5pp move -> full conviction
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
                        f"Hypothesis: {symbol}'s promoter pledge moved {delta:+.2f}pp over "
                        f"the last {TREND_WINDOW} observations; a rising pledge may be a "
                        f"red flag."
                    ),
                    evidence={
                        "pledge_delta_pp": round(delta, 4),
                        "last_pledge_pct": round(window[-1], 4),
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
            required_data=("filings",),  # pledge disclosures, no live source yet
            pit_safe=True,
            data_status="stub",
            description="NEW (stub): promoter pledge-trend red flag over the neutral "
            "'promoter_pledge' role frame; awaiting a filings data source.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = PromoterPledge()
