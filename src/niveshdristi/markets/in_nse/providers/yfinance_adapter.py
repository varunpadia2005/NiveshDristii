"""YFinance adapter for IN_NSE prices.

Market literals (.NS suffix) live ONLY in this file (gate G10 allowlist).
yfinance is an UNOFFICIAL Yahoo Finance client: personal/educational use
only, no availability guarantee (see docs/VERIFY.md section 9).

- Canonical symbols ('RELIANCE') are mapped to provider symbols here.
- raw (auto_adjust=False) and adjusted (auto_adjust=True) prices are fetched
  and stored SEPARATELY per CHANGES C3.
- Rows with NaN OHLC (observed on the live latest day) are FLAGGED, never
  dropped or filled silently.
- yfinance is imported lazily so the offline suite runs without it
  (optional 'data' extra in pyproject.toml).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import polars as pl

from niveshdristi.marketdata.client import PriceSeries

# Test seam: fetcher(symbol, start, end, auto_adjust) -> pandas-like frame
Fetcher = Callable[[str, date, date, bool], Any]


def _to_polars(df: Any) -> pl.DataFrame:
    """Normalize a pandas-like frame (DatetimeIndex + OHLCV) to polars."""
    pdf = df.reset_index()
    # The index column (named or not) is always the date column
    pdf = pdf.rename(columns={pdf.columns[0]: "date"})
    pdf.columns = [str(c).lower() for c in pdf.columns]
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in pdf.columns]
    out = pl.from_pandas(pdf[keep])
    if "date" in out.columns:
        # Normalize to plain ISO dates so lexicographic compare/order works
        out = out.with_columns(pl.col("date").cast(pl.String).str.slice(0, 10))
    return out


class YFinanceClient:
    """DataClient for IN_NSE prices backed by yfinance (unofficial)."""

    market_id = "IN_NSE"
    provider_name = "yfinance"

    # Provider suffix — market literal, allowed only in this adapter file
    _SUFFIX = ".NS"

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._fetcher = fetcher

    def _fetch(self, provider_symbol: str, start: date, end: date, auto_adjust: bool) -> Any:
        if self._fetcher is not None:
            return self._fetcher(provider_symbol, start, end, auto_adjust)
        import yfinance as yf  # lazy import: optional 'data' extra

        return yf.Ticker(provider_symbol).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=auto_adjust
        )

    def prices(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        as_of: date | None = None,
    ) -> PriceSeries:
        provider_symbol = f"{symbol}{self._SUFFIX}"
        raw = _to_polars(self._fetch(provider_symbol, start, end, auto_adjust=False))
        adjusted = _to_polars(self._fetch(provider_symbol, start, end, auto_adjust=True))

        flags: dict[str, str] = {}
        for col in ("open", "high", "low", "close"):
            if col not in raw.columns:
                continue
            bad = raw.filter(pl.col(col).is_null())
            for d in bad["date"].to_list() if bad.height else []:
                flags[str(d)[:10]] = "nan_ohl"

        if as_of is not None and "date" in raw.columns:
            cutoff = as_of.isoformat()
            raw = raw.filter(pl.col("date") <= cutoff)
            adjusted = adjusted.filter(pl.col("date") <= cutoff)

        return PriceSeries(
            symbol=symbol, market_id=self.market_id, raw=raw, adjusted=adjusted, flags=flags
        )

    def fundamentals(self, symbol: str, *, as_of: date) -> pl.DataFrame:
        """Not supported: yfinance fundamentals are current-state, no announced_at."""
        raise NotImplementedError("yfinance fundamentals lack announcement dates (PIT-unsafe)")

    def corporate_actions(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        raise NotImplementedError("corporate_actions via yfinance deferred to Phase 2+")

    def index_constituents(self, index: str, *, as_of: date) -> pl.DataFrame:
        raise NotImplementedError("yfinance has no index constituents")

    def flows(self, start: date, end: date) -> pl.DataFrame:
        raise NotImplementedError("yfinance has no FII/DII flows")

    def filings(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        raise NotImplementedError("yfinance has no exchange filings")
