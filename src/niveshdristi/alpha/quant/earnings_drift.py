"""Earnings-reaction drift model — NEW code, DATA STUB.

Hypothesis (no efficacy claim): prices may continue drifting in the
direction of the initial reaction after a quarterly announcement. The model
needs ANNOUNCEMENT-DATED results — PITRecord.announced_at — which no live
source provides today (Phase 2 P0 finding), so data_status is "stub" and
tests use synthetic PIT records plus synthetic price frames.

Drift measured as the price return from the announcement date to as_of,
clipped. Constants are UNVALIDATED DEFAULTS.
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
DRIFT_WINDOW_DAYS = 30  # announcements older than this are ignored
RETURN_CLIP = 0.20  # 20% post-announcement move = full conviction
HORIZON_DAYS = 20


class EarningsDrift:
    """Post-announcement drift over PIT announcements + price frames (NEW, stub)."""

    @property
    def model_id(self) -> str:
        return "earnings_drift"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        for symbol in inputs.fundamentals:
            if symbol not in inputs.prices:
                continue
            announcements = [r for r in inputs.fundamentals[symbol] if r.metric == "eps"]
            if not announcements:
                continue
            last = max(announcements, key=lambda r: r.announced_at)
            days = (inputs.as_of - last.announced_at).days
            if days < 0 or days > DRIFT_WINDOW_DAYS:
                continue
            closes = {
                str(d)[:10]: float(c)
                for d, c in zip(
                    inputs.prices_for(symbol)["date"].to_list(),
                    inputs.prices_for(symbol)["close"].to_list(),
                    strict=True,
                )
            }
            base = closes.get(last.announced_at.isoformat())
            last_close = closes.get(inputs.as_of.isoformat())
            if base is None or last_close is None or base == 0:
                continue
            ret = last_close / base - 1.0
            conviction = max(-1.0, min(1.0, ret / RETURN_CLIP))
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
                        f"Hypothesis: {symbol} moved {ret:+.2%} since its result "
                        f"announcement {days}d ago; the reaction may continue to drift."
                    ),
                    evidence={
                        "post_announcement_return": round(ret, 6),
                        "days_since_announcement": days,
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
            required_data=("fundamentals", "prices"),
            pit_safe=True,  # announcements visible only via as_of-filtered records
            data_status="stub",  # needs announced_at, which no source provides
            description="NEW (stub): post-announcement drift over PIT announcements "
            "and price frames; awaiting announcement-dated results.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = EarningsDrift()
