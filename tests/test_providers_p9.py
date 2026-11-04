"""P9-S4: the two-market provider registry + the US shell roles."""

from __future__ import annotations

from datetime import date

import pytest

# importing the module REGISTERS both providers
import niveshdristi.markets.providers_registry  # noqa: F401
from niveshdristi.markets.providers_registry import get_provider_for_market


class TestProviderRegistry:
    def test_lookup_by_market_id(self):
        in_cls = get_provider_for_market("IN_NSE")
        us_cls = get_provider_for_market("US_NYSE")
        assert in_cls.market_id == "IN_NSE"
        assert us_cls.market_id == "US_NYSE"

    def test_unknown_market_typed_error(self):
        with pytest.raises(KeyError, match="no provider registered"):
            get_provider_for_market("JP_TSE")

    def test_us_shell_every_role_raises(self):
        shell = get_provider_for_market("US_NYSE")()
        with pytest.raises(Exception, match="no verified US data source"):
            shell.prices("AAPL", date(2026, 1, 1), date(2026, 2, 1))
        with pytest.raises(Exception, match="fundamentals"):
            shell.fundamentals("AAPL", as_of=date(2026, 1, 1))
        for call in (
            lambda: shell.corporate_actions("AAPL", date(2026, 1, 1),
                                            date(2026, 2, 1)),
            lambda: shell.index_constituents("SPX", as_of=date(2026, 1, 1)),
            lambda: shell.flows(date(2026, 1, 1), date(2026, 2, 1)),
            lambda: shell.filings("AAPL", date(2026, 1, 1), date(2026, 2, 1)),
        ):
            with pytest.raises(Exception, match="shell role"):
                call()

    def test_shell_does_no_network(self):
        """The shell constructor with NO fetcher performs zero I/O by
        construction (no requests/urllib in the module source)."""
        from pathlib import Path

        src = (Path(__file__).resolve().parent.parent / "src"
               / "niveshdristi" / "markets" / "in_us" / "providers"
               / "us_adapter.py").read_text(encoding="utf-8")
        for banned in ("requests", "urllib", "httpx", "socket"):
            assert banned not in src
