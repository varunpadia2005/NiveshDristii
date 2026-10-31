"""Instrument — market-agnostic security identifier."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict


class Instrument(BaseModel):
    """
    Immutable security identifier.

    Attributes:
        symbol: Human-readable symbol (e.g., "RELIANCE", "AAPL")
        exchange: Exchange identifier (an ISO 10383 MIC code)
        market_id: Canonical market identifier (key into the markets registry)
        currency: ISO 4217 currency code (e.g., "INR", "USD")
        isin: International Securities Identification Number (stable across symbol changes)
        sector: Sector classification (market-specific taxonomy)
        lot_size: Minimum tradable quantity (1 for cash equities)
        tick_size: Minimum price increment
        listed_date: Date the instrument was listed (if known)
        delisted_date: Date the instrument was delisted (if applicable)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(..., min_length=1)
    exchange: str = Field(..., min_length=1)
    market_id: str = Field(..., min_length=1)
    currency: str = Field(..., min_length=1)
    isin: str | None = None
    sector: str | None = None
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.01, gt=0)
    listed_date: date | None = None
    delisted_date: date | None = None

    @field_validator("symbol", "exchange", "market_id", "currency", mode="before")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("cannot be empty")
        return v.strip()

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
