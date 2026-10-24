"""Cost engine (NEW, Phase 4) — consumes core RateSchedule only.

DOCUMENTED UNVERIFIED ASSUMPTIONS (also in docs/PROGRESS.md):
- DELIVERY trades only: the intraday transaction-levy field is ignored on
  purpose (v1 engines model delivery; a dedicated field arrives with
  intraday support).
- The delivery levy applies on BOTH buy and sell.
- Stamp duty applies on the BUY side only.
- The depository per-scrip charge (dp_charge) is applied ONCE per scrip
  per SELL order (not per day) — the simplest honest reading of "per
  scrip on sell"; verify before production.
- GST BASE = brokerage + exchange fee + regulator fee (NOT the delivery
  levy, NOT stamp duty, NOT the depository per-scrip charge — that charge
  is EXCLUDED from the GST base in this assumption).
- Slippage is reported SEPARATELY from fees (it is a modelling assumption,
  not a cash fee).

Every CostBreakdown carries rates_verified; when False the banner is
"RATES UNVERIFIED" — net-of-cost consumers must surface it.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.market_rules import RateSchedule

BANNER = "RATES UNVERIFIED"


class CostBreakdown(BaseModel):
    """Per-trade cost breakdown; amounts are plain currency floats."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    side: str  # "buy" | "sell"
    notional: float
    brokerage: float
    transaction_levy: float  # delivery levy (both sides; neutral name)
    exchange_fee: float
    regulator_fee: float
    stamp_duty: float  # buy side only
    gst: float
    dp_charge: float  # once per scrip per sell order (assumption)
    fees_total: float  # everything above EXCLUDING slippage
    slippage: float  # reported separately, never inside fees_total
    total: float  # fees_total + slippage
    rates_used: dict[str, str]  # key -> "fraction=x (y%)"
    rates_verified: bool
    banner: str | None = None

    def __init__(self, **data) -> None:
        if not data.get("rates_verified", True) and not data.get("banner"):
            data["banner"] = BANNER
        super().__init__(**data)


def _rates_used(r: RateSchedule) -> dict[str, str]:
    """Both fraction and human-percent form for every rate used."""
    pairs = {
        "brokerage_per_order": (r.brokerage_per_order, None),
        "transaction_levy_buy": (r.stt_delivery_buy, True),
        "transaction_levy_sell": (r.stt_delivery_sell, True),
        "exchange_fee": (r.exchange_fee, True),
        "regulator_fee": (r.regulator_fee, True),
        "stamp_duty_buy": (r.stamp_duty_buy, True),
        "gst_on_fees": (r.gst_on_fees, True),
        "dp_charge_per_scrip": (r.dp_charge_per_scrip, None),
        "slippage_base_bps": (r.slippage_base_bps, None),
    }
    out: dict[str, str] = {}
    for key, (value, is_fraction) in pairs.items():
        if is_fraction:
            out[key] = f"fraction={value} ({value * 100:.4g}%)"
        else:
            out[key] = f"{value}"
    return out


def compute_costs(
    *,
    side: str,
    notional: float,
    rates: RateSchedule,
    include_dp_charge: bool = False,
) -> CostBreakdown:
    """Costs for ONE delivery trade (NEW; hand-verifiable arithmetic).

    include_dp_charge: set True for a SELL that closes a scrip position for
    the day under the once-per-scrip-per-sell-order assumption.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if notional < 0:
        raise ValueError("notional must be non-negative")

    brokerage = rates.brokerage_per_order
    levy = notional * (rates.stt_delivery_buy if side == "buy" else rates.stt_delivery_sell)
    exchange_fee = notional * rates.exchange_fee
    regulator_fee = notional * rates.regulator_fee
    stamp_duty = notional * rates.stamp_duty_buy if side == "buy" else 0.0
    gst_base = brokerage + exchange_fee + regulator_fee  # NAMED ASSUMPTION
    gst = gst_base * rates.gst_on_fees
    dp_charge = rates.dp_charge_per_scrip if (side == "sell" and include_dp_charge) else 0.0

    fees_total = brokerage + levy + exchange_fee + regulator_fee + stamp_duty + gst + dp_charge
    slippage = notional * rates.slippage_base_bps / 10_000.0
    return CostBreakdown(
        side=side,
        notional=notional,
        brokerage=round(brokerage, 6),
        transaction_levy=round(levy, 6),
        exchange_fee=round(exchange_fee, 6),
        regulator_fee=round(regulator_fee, 6),
        stamp_duty=round(stamp_duty, 6),
        gst=round(gst, 6),
        dp_charge=round(dp_charge, 6),
        fees_total=round(fees_total, 6),
        slippage=round(slippage, 6),
        total=round(fees_total + slippage, 6),
        rates_used=_rates_used(rates),
        rates_verified=rates.verified,
    )
