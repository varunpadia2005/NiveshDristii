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
