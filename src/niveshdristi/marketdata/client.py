"""DataClient protocol — the market-neutral data contract (CHANGES.md C3).

Every provider (yfinance, bhavcopy files, future licensed feeds) implements
this protocol. Market-specific knowledge (symbol suffixes, file formats,
URLs) lives ONLY inside market adapter packages (e.g. markets/in_nse/),
never here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

import polars as pl

# Data kinds a provider can serve (per CHANGES C3)
DATA_KINDS = (
    "prices",
    "fundamentals",
    "corporate_actions",
    "index_constituents",
    "flows",
    "filings",
)


@dataclass(frozen=True)
class PriceSeries:
    """Prices for one instrument over a date range.

    raw: unadjusted OHLCV (split/dividend events NOT applied).
    adjusted: adjusted prices (provider convention), stored separately
    per CHANGES C3 "store raw and adjusted prices separately".
    flags: data-quality flags keyed by ISO date, e.g. "nan_ohl" — problems
    are surfaced, never silently dropped or filled.
    """

    symbol: str
    market_id: str
    raw: pl.DataFrame
    adjusted: pl.DataFrame
    flags: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class DataClient(Protocol):
    """Protocol all data providers implement. Implementations are per-market."""

    market_id: str
    provider_name: str

    def prices(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        as_of: date | None = None,
    ) -> PriceSeries:
        """Daily prices for `symbol` (canonical, suffix-less) between dates.

        as_of restricts results to data that was public by that date
        (point-in-time discipline, CHANGES C4).
        """
        ...  # pragma: no cover - protocol body

    def fundamentals(
        self,
        symbol: str,
        *,
        as_of: date,
    ) -> pl.DataFrame:
        """Fundamental records with period_end/announced_at/source columns."""
        ...  # pragma: no cover

    def corporate_actions(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Corporate actions (splits, bonuses, dividends) in the range."""
        ...  # pragma: no cover

    def index_constituents(self, index: str, *, as_of: date) -> pl.DataFrame:
        """Constituents of `index` as they were on `as_of` (survivorship-free)."""
        ...  # pragma: no cover

    def flows(self, start: date, end: date) -> pl.DataFrame:
        """Aggregate flows (e.g. FII/DII daily) in the range."""
        ...  # pragma: no cover

    def filings(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Exchange filings for `symbol` in the range."""
        ...  # pragma: no cover
