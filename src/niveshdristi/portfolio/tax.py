"""Capital-gains tax engine (NEW, Phase 4) — consumes core TaxSchedule.

Holding period uses CALENDAR-MONTH arithmetic: a sale is LONG-TERM if it is
on or after the same calendar date holding_period_months after the buy,
with the anniversary clamped to the month's last day when the buy day does
not exist in the anniversary month (e.g. a 29-Feb buy).

FY-aware loss set-off: the financial-year start MONTH is an explicit input
(no market literal in code). STCL offsets STCG then LTCG; LTCL offsets LTCG
only; unutilised losses carry forward up to loss_setoff_years. The annual
LTCG exemption applies AFTER set-off.

enabled=False returns zero tax. TaxResult carries rates_used and
rates_verified plus the banner. All rates come from TaxSchedule (YAML, all
UNVERIFIED: the 2024 rates may have changed in later budgets).
"""

from __future__ import annotations

import calendar
from datetime import date

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.market_rules import TaxSchedule
from niveshdristi.execution.costs import BANNER


class RealisedLot(BaseModel):
    """One realised gain/loss component for one symbol."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    buy_date: date
    sell_date: date
    proceeds_minus_cost: float  # realised gain (or negative for a loss)


class TaxResult(BaseModel):
    """Outcome of one financial-year tax computation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tax_due: float
    short_term_gain: float
    long_term_gain: float
    stcl_used: float
    ltcl_used: float
    stcl_carried: float
    ltcl_carried: float
    exemption_applied: float
    rates_used: dict[str, str]
    rates_verified: bool
    banner: str | None = None

    def __init__(self, **data) -> None:
        if not data.get("rates_verified", True) and not data.get("banner"):
            data["banner"] = BANNER
        super().__init__(**data)


def _add_months(buy: date, months: int) -> date:
    """Same calendar date `months` later, clamped to the month's last day."""
    total = buy.year * 12 + (buy.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(buy.day, last_day))


def is_long_term(buy: date, sell: date, schedule: TaxSchedule) -> bool:
    """True if the sale is on/after the calendar-month anniversary."""
    return sell >= _add_months(buy, schedule.holding_period_months)


def financial_year_of(day: date, fy_start_month: int) -> int:
    """The FY label year: for an April start, Feb 2027 belongs to FY 2026."""
    if fy_start_month < 1 or fy_start_month > 12:
        raise ValueError(f"fy_start_month must be 1..12, got {fy_start_month}")
    return day.year if day.month >= fy_start_month else day.year - 1


def compute_tax(
    lots: list[RealisedLot],
    schedule: TaxSchedule,
    *,
    fy_start_month: int,
    prior_stcl: float = 0.0,
    prior_ltcl: float = 0.0,
) -> TaxResult:
    """Tax for one financial year over the given realised lots (NEW)."""
    rates = {
        "short_term_rate": f"fraction={schedule.short_term_rate} "
        f"({schedule.short_term_rate * 100:.4g}%)",
        "long_term_rate": f"fraction={schedule.long_term_rate} "
        f"({schedule.long_term_rate * 100:.4g}%)",
        "holding_period_months": str(schedule.holding_period_months),
        "long_term_exemption": str(schedule.long_term_exemption),
    }
    zero = TaxResult(
        tax_due=0.0, short_term_gain=0.0, long_term_gain=0.0,
        stcl_used=0.0, ltcl_used=0.0, stcl_carried=0.0, ltcl_carried=0.0,
        exemption_applied=0.0,
        rates_used=rates, rates_verified=schedule.verified,
    )
    if not schedule.enabled:
        return zero

    st_gain = 0.0
    lt_gain = 0.0
    stcl = max(0.0, prior_stcl)
    ltcl = max(0.0, prior_ltcl)
    for lot in lots:
        if is_long_term(lot.buy_date, lot.sell_date, schedule):
            lt_gain += lot.proceeds_minus_cost
        else:
            st_gain += lot.proceeds_minus_cost

    # Split into gains and losses
    stcl_new = max(0.0, -st_gain)
    ltcl_new = max(0.0, -lt_gain)
    st_gain_pos = max(0.0, st_gain)
    lt_gain_pos = max(0.0, lt_gain)
    stcl_total = stcl + stcl_new
    ltcl_total = ltcl + ltcl_new

    # STCL offsets STCG then LTCG; LTCL offsets LTCG only
    st_offset = min(stcl_total, st_gain_pos)
    remaining_st_gain = st_gain_pos - st_offset
    stcl_after = stcl_total - st_offset
    lt_offset_by_stcl = min(stcl_after, lt_gain_pos)  # leftover STCL -> LTCG
    remaining_lt_gain = lt_gain_pos - lt_offset_by_stcl
    stcl_after -= lt_offset_by_stcl
    lt_offset_by_ltcl = min(ltcl_total, remaining_lt_gain)
    remaining_lt_gain -= lt_offset_by_ltcl
    ltcl_after = ltcl_total - lt_offset_by_ltcl

    # Annual LTCG exemption AFTER set-off
    exemption = min(schedule.long_term_exemption, max(0.0, remaining_lt_gain))
    taxable_lt = remaining_lt_gain - exemption
    taxable_st = remaining_st_gain

    # Carry-forward capped at loss_setoff_years is the CALLER's job (they
    # track age); we return the remaining carry amounts.
    tax = taxable_st * schedule.short_term_rate + taxable_lt * schedule.long_term_rate
    return TaxResult(
        tax_due=round(tax, 6),
        short_term_gain=round(st_gain, 6),
        long_term_gain=round(lt_gain, 6),
        stcl_used=round(st_offset + lt_offset_by_stcl, 6),
        ltcl_used=round(lt_offset_by_ltcl, 6),
        stcl_carried=round(stcl_after, 6),
        ltcl_carried=round(ltcl_after, 6),
        exemption_applied=round(exemption, 6),
        rates_used=rates,
        rates_verified=schedule.verified,
    )
