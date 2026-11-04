"""US_NYSE data provider SHELL (NEW, P9-S4).

Mirrors the in_nse shell exactly: every DataClient role raises a typed
NotImplemented-style error. NO network code, NO symbol-suffix logic (US
tickers need none). Composition point for a future real adapter."""

from __future__ import annotations

from datetime import date

import polars as pl

from niveshdristi.core.errors import DataError
from niveshdristi.marketdata.client import PriceSeries


class UsProviderShell:
    """DataClient shell for US_NYSE — every role raises DataError naming the
    role and the reason (no verified US source exists in this project)."""

    market_id = "US_NYSE"
    provider_name = "us-shell"

    def __init__(self, fetcher=None) -> None:
        # fetcher: the ONLY injection point a future real adapter would use
        # (mirror of the in_nse shell); the shell itself performs no I/O.
        self._fetcher = fetcher

    def prices(self, symbol: str, start: date, end: date, *,
               as_of: date | None = None) -> PriceSeries:
        raise DataError(
            "US_NYSE prices: no verified US data source exists in this "
            "project (shell role; see docs/VERIFY.md)"
        )

    def fundamentals(self, symbol: str, *, as_of: date) -> pl.DataFrame:
        raise DataError(
            "US_NYSE fundamentals: no announcement-dated source exists "
            "(shell role)"
        )

    def corporate_actions(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        raise DataError("US_NYSE corporate_actions: shell role")

    def index_constituents(self, index: str, *, as_of: date) -> pl.DataFrame:
        raise DataError("US_NYSE index_constituents: shell role")

    def flows(self, start: date, end: date) -> pl.DataFrame:
        raise DataError("US_NYSE flows: shell role")

    def filings(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        raise DataError("US_NYSE filings: shell role")
