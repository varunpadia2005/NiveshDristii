"""Fundamental guardrails model — PORT of the legacy RULES MATHS only.

PORTED (legacy maths, imported read-only, unchanged):
- niveshdristi.fundamentals.loader.check_guardrails (line 119): the
  CFG-driven rule evaluation producing flags and a max score cap.
  The legacy FETCH path is NOT called (it is network + PG + as_of=today(),
  i.e. legacy, not PIT-safe); this model is fed exclusively by PITStore
  records queried at ctx/inputs as_of.

NEW (not a port):
- Quality score derived from the guardrail report (the legacy has no score,
  only a max_score_cap): start at 100, minus a penalty per warn/error flag.
- Hard exclusion: any 'error'-severity flag marks the symbol excluded.
- Signal mapping: conviction = (quality - 50) / 50, clipped to [-1, 1].

Registry data_status is "stub": no announcement-dated fundamentals source
exists yet (Phase 2 P0 finding), so real-data use is not possible; tests use
synthetic PITStore fixtures only. Constants are UNVALIDATED DEFAULTS; theses
state hypotheses only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal
from niveshdristi.data.contracts import FundamentalData  # legacy contract type (dataclass)
from niveshdristi.fundamentals.loader import check_guardrails  # legacy rules maths (PORT)

# UNVALIDATED DEFAULTS (NEW code)
WARN_PENALTY = 20  # quality-score points lost per 'warn' flag
ERROR_PENALTY = 40  # quality-score points lost per 'error' flag
HORIZON_DAYS = 60  # fundamentals change slowly

# FundamentalData fields fillable from PIT records (neutral metric names)
_PIT_METRICS = ("pe_ratio", "pb_ratio", "roe", "debt_to_equity", "profit_margin", "revenue_growth")


def quality_score(max_score_cap: int, flags: list[dict]) -> tuple[int, bool]:
    """NEW: quality score 0..100 from guardrail flags; hard exclusion flag."""
    score = 100
    for f in flags:
        score -= WARN_PENALTY if f.get("severity") == "warn" else ERROR_PENALTY
    score = max(0, min(score, max_score_cap))
    excluded = any(f.get("severity") == "error" for f in flags)
    return score, excluded


class FundamentalGuardrails:
    """Quality score + hard exclusions over PIT fundamentals (PORT of rules maths)."""

    @property
    def model_id(self) -> str:
        return "fundamental_guardrails"

    def legacy_report(self, fund: FundamentalData):
        """Direct legacy call (ported maths): CFG-driven guardrail rules."""
        return check_guardrails(fund)

    def _fund_from_pit(self, symbol: str, records: tuple) -> FundamentalData | None:
        """Build the legacy contract object from PIT records (NEW glue)."""
        latest: dict = dict.fromkeys(_PIT_METRICS)
        for rec in records:  # records are already as_of-filtered by the caller
            if rec.metric in latest and rec.value is not None:
                latest[rec.metric] = rec.value
        if all(v is None for v in latest.values()):
            return None
        return FundamentalData(
            ticker=symbol,
            pe_ratio=latest["pe_ratio"],
            pb_ratio=latest["pb_ratio"],
            roe=latest["roe"],
            debt_to_equity=latest["debt_to_equity"],
            profit_margin=latest["profit_margin"],
            revenue_growth=latest["revenue_growth"],
            sector="Unknown",
            as_of=date.min,  # placeholder; PIT discipline handled by the caller
        )

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in inputs.fundamentals:
            records = inputs.fundamentals[symbol]
            fund = self._fund_from_pit(symbol, records)
            if fund is None:
                continue
            report = self.legacy_report(fund)  # PORTED maths
            score, excluded = quality_score(report.max_score_cap, report.flags)  # NEW
            conviction = max(-1.0, min(1.0, (score - 50) / 50))  # NEW mapping
            if conviction == 0.0:
                continue
            stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
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
                        f"Hypothesis: {symbol}'s fundamentals score {score}/100 on the "
                        f"ported guardrail rules"
                        + (" with a HARD EXCLUSION flag" if excluded else "")
                        + ", which may indicate quality."
                    ),
                    evidence={
                        "quality_score": score,
                        "hard_exclusion": excluded,
                        "flag_count": len(report.flags),
                        "max_score_cap": report.max_score_cap,
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
            pit_safe=True,  # mechanically PIT-safe via as_of-filtered records
            data_status="stub",  # no announcement-dated source exists (P0 finding)
            description="PORT of legacy check_guardrails rules maths over PITStore "
            "records; quality score and exclusion mapping are NEW. Legacy fetch "
            "path (network/PG/as_of=today) is legacy, not PIT-safe, and unused.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = FundamentalGuardrails()
