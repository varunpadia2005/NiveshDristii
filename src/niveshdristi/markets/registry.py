"""MarketProfile registry — maps market_id to MarketProfile."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import time
from typing import Optional
from pathlib import Path

from niveshdristi.core.instrument import Instrument


@dataclass(frozen=True, slots=True)
class SessionTimes:
    """Trading session times (in market timezone)."""
    pre_open: Optional[time] = None
    open: time = time(9, 15)
    close: time = time(15, 30)
    post_close: Optional[time] = None


@dataclass(frozen=True, slots=True)
class SettlementConfig:
    """Settlement configuration."""
    cycle: str = "T+1"  # e.g., "T+1", "T+2"
    days: int = 1


@dataclass(frozen=True, slots=True)
class PriceLimitConfig:
    """Price limit / circuit breaker configuration."""
    enabled: bool = True
    default_bands: tuple[float, ...] = (0.02, 0.05, 0.10, 0.20)  # 2%, 5%, 10%, 20%
    index_bands: tuple[float, ...] = (0.10, 0.15, 0.20)  # For index


@dataclass(frozen=True, slots=True)
class CostModel:
    """Transaction cost model (all values as fractions, e.g., 0.001 = 10 bps)."""
    # Brokerage
    brokerage_per_order: float = 0.0  # Fixed fee per order (in currency units)
    brokerage_pct: float = 0.0  # Percentage of notional
    brokerage_min: float = 0.0
    brokerage_max: float = float("inf")

    # Regulatory / exchange
    stt_pct: float = 0.0  # Securities Transaction Tax (on sell side for delivery)
    exchange_charges_pct: float = 0.0
    sebi_fees_pct: float = 0.0
    stamp_duty_pct: float = 0.0  # On buy side
    gst_pct: float = 0.0  # On brokerage + exchange charges

    # Slippage / market impact
    slippage_bps: float = 0.0  # Base slippage in basis points

    # Depository
    dp_charge_per_scrip: float = 0.0  # Per scrip on sell (in currency units)

    def total_round_trip_bps(self, notional: float = 1_00_000) -> float:
        """Estimate total round-trip cost in basis points for a given notional."""
        # Buy costs
        buy_cost = (
            self.brokerage_per_order
            + notional * self.brokerage_pct
            + notional * self.exchange_charges_pct
            + notional * self.sebi_fees_pct
            + notional * self.stamp_duty_pct
        )
        # Sell costs
        sell_cost = (
            self.brokerage_per_order
            + notional * self.brokerage_pct
            + notional * self.exchange_charges_pct
            + notional * self.sebi_fees_pct
            + notional * self.stt_pct
        )
        # GST on brokerage + exchange charges
        gst_base = (
            notional * (self.brokerage_pct + self.exchange_charges_pct) * 2
            + self.brokerage_per_order * 2
        )
        gst = gst_base * self.gst_pct
        total = buy_cost + sell_cost + gst + self.dp_charge_per_scrip + notional * self.slippage_bps / 10_000
        return (total / notional) * 10_000


@dataclass(frozen=True, slots=True)
class TaxModel:
    """Capital gains tax model (optional, can be None for tax-free accounts)."""
    enabled: bool = True
    short_term_threshold_days: int = 365
    short_term_rate: float = 0.20  # 20%
    long_term_rate: float = 0.125  # 12.5%
    long_term_exemption: float = 1_25_000  # Annual exemption (in currency units)
    loss_setoff_years: int = 8
    # STCG can offset STCG and LTCG; LTCL can only offset LTCG


@dataclass(frozen=True, slots=True)
class MarketProfile:
    """
    Complete market definition — the single source of truth for all market-specific rules.

    Adding a new market = adding one MarketProfile + one data adapter + one cost model.
    NO market-specific logic should exist in core/ or engine/.
    """

    market_id: str  # e.g., "IN_NSE", "US_NYSE"
    name: str  # Human-readable name
    timezone: str  # IANA timezone (e.g., "Asia/Kolkata", "America/New_York")
    currency: str  # ISO 4217 (e.g., "INR", "USD")
    session: SessionTimes = field(default_factory=SessionTimes)
    settlement: SettlementConfig = field(default_factory=SettlementConfig)
    price_limits: PriceLimitConfig = field(default_factory=PriceLimitConfig)
    cost_model: CostModel = field(default_factory=CostModel)
    tax_model: Optional[TaxModel] = None

    # Shorting rules
    shorting_allowed: bool = False  # Cash segment shorting
    intraday_shorting_allowed: bool = True  # Intraday only

    # Calendar & holidays (loaded from YAML)
    calendar_path: Optional[str] = None  # Path to holidays YAML

    # Universe & benchmark
    default_universe: str = "default"  # Key in universes/
    benchmark_symbol: str = ""  # e.g., "^NSEI", "^GSPC"
    benchmark_is_total_return: bool = True  # Prefer TRI over price index

    # Sector taxonomy (loaded from YAML)
    sector_taxonomy_path: Optional[str] = None

    # Exclusion lists (loaded from YAML)
    asm_gsm_path: Optional[str] = None  # Surveillance lists
    fno_ban_path: Optional[str] = None  # F&O ban list

    # Minimum filters
    min_price: float = 1.0
    min_market_cap: float = 0.0
    min_adv_crores: float = 0.0  # Average daily volume in crores

    # Data provider suffix mapping (provider-specific, NOT in core)
    # e.g., {"yfinance": ".NS", "nse": ""}
    provider_suffixes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.market_id:
            raise ValueError("market_id is required")
        if not self.timezone:
            raise ValueError("timezone is required")
        if not self.currency:
            raise ValueError("currency is required")


class MarketRegistry:
    """Registry of all known market profiles."""

    def __init__(self):
        self._profiles: dict[str, MarketProfile] = {}

    def register(self, profile: MarketProfile) -> None:
        if profile.market_id in self._profiles:
            raise ValueError(f"Market profile already registered: {profile.market_id}")
        self._profiles[profile.market_id] = profile

    def get(self, market_id: str) -> MarketProfile:
        if market_id not in self._profiles:
            raise KeyError(f"Unknown market_id: {market_id}. Available: {list(self._profiles.keys())}")
        return self._profiles[market_id]

    def __contains__(self, market_id: str) -> bool:
        return market_id in self._profiles

    def list_markets(self) -> list[str]:
        return list(self._profiles.keys())


# Global registry instance
_REGISTRY = MarketRegistry()


def get_registry() -> MarketRegistry:
    return _REGISTRY


def register_market(profile: MarketProfile) -> None:
    _REGISTRY.register(profile)