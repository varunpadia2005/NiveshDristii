"""Delivery-percentage anomaly model — NEW code (India-specific, literal-free).

Consumes an aux frame BY ROLE: inputs.aux["delivery"] with NEUTRAL column
names (symbol, date, delivery_pct). The translation from the bhavcopy
parser's market-specific column names happens ONLY inside the allowlisted
adapter (markets/in_nse/providers/bhavcopy_file.to_delivery_frame).

Hypothesis (no efficacy claim): an abnormally HIGH delivery percentage may
indicate accumulation. All constants are UNVALIDATED DEFAULTS; the model is
pure on the frames supplied to it (registry data_status 'live' — it computes
purely from the aux frame; obtaining real frames requires manually
downloaded bhavcopy files per the exchange terms noted in docs/VERIFY.md §9).
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
Z_WINDOW = 20  # trailing sessions for the delivery-% baseline
Z_CAP = 3.0  # |z| beyond this clips to full conviction
HORIZON_DAYS = 10


def delivery_zscore(series: list[float]) -> float | None:
    """z-score of the LAST delivery_pct vs the trailing Z_WINDOW population."""
    window = series[-Z_WINDOW:]
    if len(window) < Z_WINDOW:
        return None
    mean = sum(window) / Z_WINDOW
    var = sum((v - mean) ** 2 for v in window) / Z_WINDOW
    if var == 0:
        return None
    z: float = (window[-1] - mean) / (var ** 0.5)
    return z


class DeliveryAnomaly:
    """Delivery-% anomaly model over the 'delivery' role frame (NEW)."""

    @property
    def model_id(self) -> str:
        return "delivery_anomaly"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        delivery = inputs.aux.get("delivery")
        if not isinstance(delivery, pl.DataFrame):
            return []  # role not supplied: no opinion
        if not {"symbol", "date", "delivery_pct"}.issubset(delivery.columns):
            return []

        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        signals: list[Signal] = []
        for symbol in inputs.prices:
            rows = delivery.filter(pl.col("symbol") == symbol).sort("date")
            series = [float(v) for v in rows["delivery_pct"].to_list() if v is not None]
            z = delivery_zscore(series)
            if z is None:
                continue
            conviction = max(-1.0, min(1.0, z / Z_CAP))  # high delivery -> positive
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
                        f"Hypothesis: {symbol}'s delivery percentage is {z:.2f} std devs "
                        f"above its {Z_WINDOW}-session baseline, which may indicate "
                        f"accumulation."
                    ),
                    evidence={
                        "delivery_z": round(z, 6),
                        "last_delivery_pct": round(series[-1], 4),
                        "window": Z_WINDOW,
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),  # delivery arrives via the 'delivery' aux role
            pit_safe=True,
            data_status="live",  # pure on supplied frames (files via manual download)
            description="NEW: delivery-percentage anomaly over the neutral 'delivery' "
            "role frame; bhavcopy column mapping lives in the allowlisted adapter.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = DeliveryAnomaly()
