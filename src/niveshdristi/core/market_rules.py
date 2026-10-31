"""Neutral market-rules view for portfolio/ and execution/ (NEW, Phase 4).

Market-neutral, literal-free types: everything neutral code needs from a
market (rate schedule, tax schedule, price-limit rule, exclusions, basic
rules) expressed in FRACTIONS or plain currency amounts — never percents.
markets/ converts its MarketProfile into these via MarketProfile.to_rules();
portfolio/ and execution/ never import markets/ (import-boundary test).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict

from niveshdristi.core.instrument import Instrument


def _require_verification_source(verified: bool, source: str, verified_on: date | None) -> None:
    """verified=True requires a non-empty source AND a verified_on date."""
    if verified and (not source or not source.strip() or verified_on is None):
        raise ValueError(
            "verified=True requires a non-empty source and a verified_on date "
            "(unverified schedules must stay verified=False)"
        )


class RateSchedule(BaseModel):
    """Transaction-cost rates — ALL fractions or plain currency amounts.

    Units (stated per field because the YAML keys carry a misleading *_pct
    suffix for fraction values; see docs/PROGRESS.md units audit):
      - *_rate / *_fee / *_duty / gst_on_fees: fractions of notional
        (0.001 = 0.1% = 10 bps)
      - brokerage_per_order, dp_charge_per_scrip: currency amounts per event
      - slippage_base_bps: basis points (5.0 = 5 bps)
    v1 is DELIVERY-ONLY: no separate intraday transaction-levy field exists
    because the Phase 4 engines model delivery trades only; when intraday is
    added, a dedicated field must be introduced (documented, not silently
    reused). Field names here are neutral; market-specific tax terminology
    lives in markets/.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    brokerage_per_order: float = Field(default=0.0, ge=0)
    stt_delivery_buy: float = Field(default=0.0, ge=0)  # fraction of notional
    stt_delivery_sell: float = Field(default=0.0, ge=0)  # fraction of notional
    exchange_fee: float = Field(default=0.0, ge=0)  # fraction of notional
    regulator_fee: float = Field(default=0.0, ge=0)  # fraction of notional
    stamp_duty_buy: float = Field(default=0.0, ge=0)  # fraction of notional
    gst_on_fees: float = Field(default=0.0, ge=0)  # fraction of fee base
    dp_charge_per_scrip: float = Field(default=0.0, ge=0)  # currency per scrip
    slippage_base_bps: float = Field(default=0.0, ge=0)  # basis points

    verified: bool = False
    source: str = ""
    verified_on: date | None = None

    @model_validator(mode="after")
    def _verified_needs_source(self) -> RateSchedule:
        _require_verification_source(self.verified, self.source, self.verified_on)
        return self


class TaxSchedule(BaseModel):
    """Capital-gains tax schedule — rates are fractions, amounts currency.

    holding_period_months is the OPERATIONAL 12-month assumption (UNVERIFIED
    economic/legal assumption); short_term_threshold_days is kept for
    reference to the source YAML and must be consistent with it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    holding_period_months: int = Field(default=12, ge=1)  # UNVERIFIED assumption
    short_term_threshold_days: int = Field(default=365, ge=1)  # reference only
    short_term_rate: float = Field(default=0.0, ge=0)  # fraction
    long_term_rate: float = Field(default=0.0, ge=0)  # fraction
    long_term_exemption: float = Field(default=0.0, ge=0)  # currency per FY
    loss_setoff_years: int = Field(default=0, ge=0)

    verified: bool = False
    source: str = ""
    verified_on: date | None = None

    @model_validator(mode="after")
    def _verified_needs_source(self) -> TaxSchedule:
        _require_verification_source(self.verified, self.source, self.verified_on)
        return self


class PriceLimitRule(BaseModel):
    """Circuit/price-band rule: bands are fractions (0.10 = 10%)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    bands: tuple[float, ...] = ()


class ExclusionList(BaseModel):
    """Symbols excluded from trading, as-of dated, with a source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: frozenset[str] = frozenset()
    as_of: date | None = None
    source: str = ""


class MarketRules(BaseModel):
    """Everything neutral portfolio/execution code needs from a market.

    min_adv is in PLAIN currency units (the markets/ side converts from
    crores). settlement_days is the T+N integer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    market_id: str
    shorting_allowed: bool = False
    min_price: float = Field(default=0.0, ge=0)  # currency
    min_adv: float = Field(default=0.0, ge=0)  # currency (plain units)
    settlement_days: int = Field(default=1, ge=0)
    rates: RateSchedule = Field(default_factory=RateSchedule)
    tax: TaxSchedule | None = None
    price_limits: PriceLimitRule = Field(default_factory=PriceLimitRule)
    exclusions: ExclusionList = Field(default_factory=ExclusionList)

    def is_excluded(self, instrument: Instrument) -> bool:
        """True if the instrument's symbol is on the exclusion list."""
        return instrument.symbol in self.exclusions.symbols
