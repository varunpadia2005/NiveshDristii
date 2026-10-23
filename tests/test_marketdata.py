"""
Test the market-neutral data layer: DataClient protocol + provider registry.

Protects the rules that (1) the protocol is implementable by fakes with no
network, (2) chains are ordered and config-driven, and (3) unknown kinds or
providers fail loudly.
"""

from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.marketdata.client import DataClient, PriceSeries
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
                base = {
                    k: [v * 0.5 if v is not None else None for v in vs]
                    for k, vs in base.items()
                }
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


class TestBhavcopyFileParser:
    """IN_NSE bhavcopy file parser: schema-typed, date-keyed, loud on mismatch."""

    FIXTURE = Path("tests/fixtures/bhavcopy_SYNTHETIC_sec_bhavdata_full.csv")

    def test_parses_synthetic_fixture_with_real_schema(self):
        from niveshdristi.markets.in_nse.providers.bhavcopy_file import parse_bhavcopy_csv

        df = parse_bhavcopy_csv(self.FIXTURE)
        assert df.height == 3
        assert df["DELIV_QTY"].dtype == pl.Int64
        assert df["DELIV_PER"].dtype == pl.Float64
        assert df["DATE1"].to_list() == [date(2026, 10, 23)] * 3  # date-keyed

    def test_schema_mismatch_fails_loudly(self, tmp_path):
        from niveshdristi.core.errors import ProviderError
        from niveshdristi.markets.in_nse.providers.bhavcopy_file import parse_bhavcopy_csv

        bad = tmp_path / "bad.csv"
        bad.write_text(
            "SYMBOL,DATE1,CLOSE_PRICE,WRONG_COL\nTESTA,23-Oct-2026,100.0,1\n", encoding="utf-8"
        )
        with pytest.raises(ProviderError, match="schema mismatch"):
            parse_bhavcopy_csv(bad)

    def test_delivery_for_symbol_and_missing_file(self, tmp_path):
        from niveshdristi.core.errors import ProviderError
        from niveshdristi.markets.in_nse.providers.bhavcopy_file import BhavcopyFileStore

        store = BhavcopyFileStore(tmp_path)
        (tmp_path / "sec_bhavdata_full_23102026.csv").write_text(
            self.FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        assert store.available_dates() == [date(2026, 10, 23)]
        d = store.delivery_for("TESTA", date(2026, 10, 23))
        assert d.height == 1
        assert d["DELIV_QTY"].to_list() == [40000]
        assert d["DELIV_PER"].to_list() == [40.0]
        with pytest.raises(ProviderError, match="not found"):
            store.load_day(date(2026, 10, 22))


class TestParquetCache:
    """Parquet cache: deterministic keys, hit on second call, staleness, as_of."""

    @staticmethod
    def _df(n: int = 2) -> pl.DataFrame:
        dates = [f"2026-10-2{i}" for i in range(n)]
        return pl.DataFrame({"date": dates, "close": [100.0 + i for i in range(n)]})

    def test_second_identical_call_hits_cache(self, tmp_path):
        from niveshdristi.marketdata.cache import ParquetCache, cache_key

        cache = ParquetCache(tmp_path)
        calls = []

        def fetch():
            calls.append(1)
            return self._df()

        key = cache_key("prices", "M", "X", date(2026, 1, 1), date(2026, 1, 31))
        r1 = cache.get_or_fetch(key, fetch)
        r2 = cache.get_or_fetch(key, fetch)
        assert r1.equals(r2)
        assert len(calls) == 1  # second call was a cache hit
        assert list(tmp_path.glob("*.parquet"))  # written under tmp_path only

    def test_as_of_changes_the_key(self, tmp_path):
        from niveshdristi.marketdata.cache import ParquetCache, cache_key

        base = (date(2026, 1, 1), date(2026, 1, 31))
        k1 = cache_key("prices", "M", "X", *base, as_of=date(2026, 2, 1))
        k2 = cache_key("prices", "M", "X", *base, as_of=date(2026, 3, 1))
        assert k1 != k2
        cache = ParquetCache(tmp_path)
        assert cache.get(k1) is None
        assert cache.get(k2) is None

    def test_as_of_pinned_entries_never_stale_live_entries_do(self, tmp_path):
        """The immutability rule is applied by prices(): as_of-pinned reads
        ignore live_max_age; live reads honour it."""
        from niveshdristi.marketdata.cache import ParquetCache

        cache = ParquetCache(tmp_path)
        zero_age = timedelta(0)
        calls = []

        def fetch():
            calls.append(1)
            return self._df()

        args = (date(2026, 1, 1), date(2026, 1, 31))
        # as_of-pinned: second read is a hit even with live_max_age=0
        r1 = cache.prices("M", "X", *args, fetch, as_of=date(2026, 2, 1), live_max_age=zero_age)
        r2 = cache.prices("M", "X", *args, fetch, as_of=date(2026, 2, 1), live_max_age=zero_age)
        assert r1.equals(r2)
        assert len(calls) == 1
        # live: max_age=0 means always stale -> fetch again
        cache.prices("M", "X", *args, fetch, live_max_age=zero_age)
        cache.prices("M", "X", *args, fetch, live_max_age=zero_age)
        assert len(calls) == 3  # 1 as_of fetch + 2 live fetches
