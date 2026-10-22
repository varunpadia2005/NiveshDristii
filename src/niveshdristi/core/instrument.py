"""Instrument — market-agnostic security identifier."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True, slots=True)
class Instrument:
    """
    Immutable security identifier.

    Attributes:
        symbol: Human-readable symbol (e.g., "RELIANCE", "AAPL")
        exchange: Exchange code (e.g., "NSE", "NYSE", "NASDAQ")
        market_id: Canonical market identifier (e.g., "IN_NSE", "US_NYSE")
        currency: ISO 4217 currency code (e.g., "INR", "USD")
        isin: International Securities Identification Number (stable across symbol changes)
        sector: Sector classification (market-specific taxonomy)
        lot_size: Minimum tradable quantity (1 for cash equities)
        tick_size: Minimum price increment
        listed_date: Date the instrument was listed (if known)
        delisted_date: Date the instrument was delisted (if applicable)
    """

    symbol: str
    exchange: str
    market_id: str
    currency: str
    isin: Optional[str] = None
    sector: Optional[str] = None
    lot_size: int = 1
    tick_size: float = 0.01
    listed_date: Optional[date] = None
    delisted_date: Optional[date] = None

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if not self.exchange:
            raise ValueError("exchange cannot be empty")
        if not self.market_id:
            raise ValueError("market_id cannot be empty")
        if not self.currency:
            raise ValueError("currency cannot be empty")
        if self.lot_size < 1:
            raise ValueError("lot_size must be >= 1")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be > 0")

    @property
    def is_active(self) -> bool:
        """True if not delisted (or delisting date unknown)."""
        return self.delisted_date is None

    def __str__(self) -> str:
        return f"{self.symbol}.{self.exchange}"

    def __repr__(self) -> str:
        return (
            f"Instrument(symbol={self.symbol!r}, exchange={self.exchange!r}, "
            f"market_id={self.market_id!r}, currency={self.currency!r}, isin={self.isin!r})"
        )