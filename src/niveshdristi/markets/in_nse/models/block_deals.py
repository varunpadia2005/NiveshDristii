"""Bulk/block deal model — NEW code, DATA STUB.

Deal prints via a neutral aux frame by ROLE: inputs.aux["block_deals"] with
columns (symbol, date, premium_pct) — premium_pct is the deal price relative
to the session price (positive = deal struck at a premium).

Hypothesis (no efficacy claim): a recent block deal at a premium may signal
informed demand -> positive conviction. No live deals source exists (Phase 2
P0: filings/bulk-deal sources blocked), so data_status is "stub" —
fixture-driven only. Constants are UNVALIDATED DEFAULTS.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
RECENCY_DAYS = 30  # deals older than this are ignored
PREMIUM_SCALE = 5.0  # premium % for full conviction
HORIZON_DAYS = 20


class BlockDeals:
    """Recent block-deal premium model over the 'block_deals' role frame."""

    @property
    def model_id(self) -> str:
        return "block_deals"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        frame = inputs.aux.get("block_deals")
        if not isinstance(frame, pl.DataFrame):
            return []
        if not {"symbol", "date", "premium_pct"}.issubset(frame.columns):
            return []
        cutoff = inputs.as_of.isoformat()
        recent = frame.filter(pl.col("date").cast(pl.String).str.slice(0, 10) <= cutoff)
        # recency vs as_of in days is checked via date distance at call time
        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)

        signals: list[Signal] = []
        for symbol in inputs.prices:
            rows = recent.filter(pl.col("symbol") == symbol).sort("date")
            if rows.height == 0:
                continue
            last = rows.tail(1)
            deal_day = str(last["date"].to_list()[0])[:10]
            days_old = (inputs.as_of - _parse_iso(deal_day)).days
            if days_old > RECENCY_DAYS or days_old < 0:
                continue
            premium = float(last["premium_pct"].to_list()[0])
            conviction = max(-1.0, min(1.0, premium / PREMIUM_SCALE))
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
                        f"Hypothesis: {symbol} had a block deal {days_old}d ago at "
                        f"{premium:+.2f}% to session price, which may signal informed "
                        f"demand."
                    ),
                    evidence={
                        "deal_premium_pct": round(premium, 4),
                        "days_old": days_old,
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
            required_data=("filings",),  # bulk/block deal disclosures; no source yet
            pit_safe=True,
            data_status="stub",
            description="NEW (stub): recent block-deal premium over the neutral "
            "'block_deals' role frame; awaiting a deals data source.",
        )


def _parse_iso(day: str):
    from datetime import date as _date

    return _date.fromisoformat(day)


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = BlockDeals()
