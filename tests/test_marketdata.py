"""
Test the market-neutral data layer: DataClient protocol + provider registry.

Protects the rules that (1) the protocol is implementable by fakes with no
network, (2) chains are ordered and config-driven, and (3) unknown kinds or
providers fail loudly.
"""

from datetime import date

import polars as pl
import pytest

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.marketdata.client import DATA_KINDS, DataClient, PriceSeries
from niveshdristi.marketdata.registry import ProviderRegistry, default_registry


class FakeProvider:
    """Offline DataClient used by tests; serves empty frames."""

    market_id = "TEST_MARKET"
    provider_name = "fake"

    def prices(self, symbol, start, end, *, as_of=None):
        empty = pl.DataFrame({"date": [], "close": []})
        return PriceSeries(symbol=symbol, market_id=self.market_id, raw=empty, adjusted=empty)

    def fundamentals(self, symbol, *, as_of):
        return pl.DataFrame()

    def corporate_actions(self, symbol, start, end):
        return pl.DataFrame()

    def index_constituents(self, index, *, as_of):
        return pl.DataFrame()

    def flows(self, start, end):
        return pl.DataFrame()

    def filings(self, symbol, start, end):
        return pl.DataFrame()


class TestProtocol:
    def test_fake_satisfies_protocol(self):
        """A network-free fake implements DataClient (runtime checkable)."""
        assert isinstance(FakeProvider(), DataClient)

    def test_price_series_holds_raw_and_adjusted_separately(self):
        empty = pl.DataFrame({"date": [], "close": []})
        ps = PriceSeries(symbol="X", market_id="M", raw=empty, adjusted=empty)
        assert ps.raw.shape == (0, 2)
        assert ps.adjusted.shape == (0, 2)


class TestRegistry:
    def test_chain_preserves_order(self):
        """Chain order is exactly what was configured."""
        reg = ProviderRegistry()
        reg.register_factory("a", FakeProvider)
        reg.register_factory("b", FakeProvider)
        reg.set_chain("M", "prices", ["b", "a"])
        assert reg.chain_names("M", "prices") == ["b", "a"]
        clients = reg.chain("M", "prices")
        assert [c.provider_name for c in clients] == ["fake", "fake"]

    def test_unknown_kind_rejected(self):
        reg = ProviderRegistry()
        with pytest.raises(ConfigurationError):
            reg.set_chain("M", "not_a_kind", [])

    def test_unknown_provider_rejected(self):
        reg = ProviderRegistry()
        with pytest.raises(ConfigurationError, match="unregistered"):
            reg.set_chain("M", "prices", ["ghost"])

    def test_default_registry_from_dicts(self):
        reg = default_registry(
            factories={"fake": FakeProvider},
            chains={("M", "prices"): ["fake"]},
        )
        assert reg.chain_names("M", "prices") == ["fake"]

    def test_empty_chain_when_unset(self):
        reg = ProviderRegistry()
        assert reg.chain("M", "prices") == []


class TestYFinanceAdapter:
    """IN_NSE yfinance adapter: suffix mapping, raw/adjusted split, NaN flags."""

    @staticmethod
    def _make_fetcher(calls):
        import pandas as pd

        def fetcher(symbol, start, end, auto_adjust):
            calls.append((symbol, auto_adjust))
            idx = pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"])
            base = {
                "Open": [100.0, 101.0, None],
                "High": [101.0, 102.0, None],
                "Low": [99.0, 100.0, None],
                "Close": [100.5, 101.5, None],  # latest day: NaN OHLC (live-observed)
                "Volume": [1000, 1100, 1200],
            }
            if auto_adjust:
                base = {k: [v * 0.5 if v is not None else None for v in vs] for k, vs in base.items()}
            return pd.DataFrame(base, index=idx)

        return fetcher

    def test_suffix_mapping_inside_adapter(self):
        """Canonical RELIANCE -> provider symbol RELIANCE.NS (adapter only)."""
        from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

        calls: list = []
        client = YFinanceClient(fetcher=self._make_fetcher(calls))
        client.prices("RELIANCE", date(2026, 10, 20), date(2026, 10, 23))
        symbols = {c[0] for c in calls}
        assert symbols == {"RELIANCE.NS"}
        # raw + adjusted are two separate fetches
        assert sorted(c[1] for c in calls) == [False, True]

    def test_raw_and_adjusted_stored_separately(self):
        from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

        client = YFinanceClient(fetcher=self._make_fetcher([]))
        ps = client.prices("RELIANCE", date(2026, 10, 20), date(2026, 10, 23))
        assert ps.raw["close"].to_list()[0] == pytest.approx(100.5)
        assert ps.adjusted["close"].to_list()[0] == pytest.approx(50.25)
        assert ps.market_id == "IN_NSE"

    def test_nan_ohl_rows_flagged_not_dropped(self):
        from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

        client = YFinanceClient(fetcher=self._make_fetcher([]))
        ps = client.prices("RELIANCE", date(2026, 10, 20), date(2026, 10, 23))
        assert ps.raw.height == 3  # row kept
        assert ps.flags.get("2026-10-23") == "nan_ohl"

    def test_as_of_filters_rows(self):
        from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

        client = YFinanceClient(fetcher=self._make_fetcher([]))
        ps = client.prices(
            "RELIANCE", date(2026, 10, 20), date(2026, 10, 23), as_of=date(2026, 10, 22)
        )
        assert ps.raw.height == 2
        assert ps.raw["date"].max() <= "2026-10-22"

    def test_unsupported_kinds_raise_not_implemented(self):
        from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

        client = YFinanceClient(fetcher=self._make_fetcher([]))
        with pytest.raises(NotImplementedError):
            client.fundamentals("RELIANCE", as_of=date(2026, 10, 23))
        with pytest.raises(NotImplementedError):
            client.index_constituents("NIFTY 50", as_of=date(2026, 10, 23))
