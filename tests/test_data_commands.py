"""P12-A: the data/signals CLI commands (previously interface-stability
stubs) implemented through the market DataClient seams.

Offline: the IN_NSE yfinance adapter's _fetch is monkeypatched (same
pattern as test_fetch_window); the US_NYSE shell needs no network (it
raises a typed DataError by design).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import pytest
from typer.testing import CliRunner

from niveshdristi.cli.main import app

runner = CliRunner()


def _fake_yf_frame(days: int, end: date) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=days, freq="D")
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [1_000_000] * n,
        },
        index=idx,
    )


@pytest.fixture
def fake_in_nse(monkeypatch):
    """Patch the IN_NSE adapter's low-level fetch (no network)."""
    calls: list[tuple[str, str, str]] = []

    class _FakeFetch:
        def _fetch(self, provider_symbol, start, end, auto_adjust):
            calls.append((provider_symbol, str(start), str(end)))
            return _fake_yf_frame(30, end)

    monkeypatch.setattr(
        "niveshdristi.markets.in_nse.providers.yfinance_adapter.YFinanceClient._fetch",
        _FakeFetch._fetch,
    )
    return calls


END = date.today() - timedelta(days=3)
START = END - timedelta(days=30)


class TestDataFetch:
    def test_fetch_reports_rows_per_symbol(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE", "TCS",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok"
        assert data["provider"] == "yfinance"
        assert data["market"] == "IN_NSE"
        syms = {s["symbol"]: s for s in data["symbols"]}
        assert set(syms) == {"RELIANCE", "TCS"}
        for s in syms.values():
            assert s["rows"] > 0
            assert s["first"] <= s["last"]

    def test_fetch_passes_bounded_window_to_the_adapter(
        self, fake_in_nse, tmp_path
    ):
        runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert fake_in_nse, "the adapter must have been called"
        for _sym, s, e in fake_in_nse:
            assert date.fromisoformat(s) == START
            assert date.fromisoformat(e) == END

    def test_fetch_us_market_typed_refusal(self, tmp_path):
        """US_NYSE: the shell provider raises a typed DataError — never a
        silent empty result."""
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "AAPL",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--market", "US_NYSE"],
        )
        assert r.exit_code == 1, r.output
        data = json.loads(r.output)
        assert data["status"] == "error"
        assert "US_NYSE" in data["error"]

    def test_fetch_unknown_market_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--market", "NOPE"],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"
        assert "NOPE" in data["error"]

    def test_fetch_missing_dates_usage_error(self, tmp_path):
        r = runner.invoke(app, ["--json", "data", "fetch", "RELIANCE"])
        assert r.exit_code == 2

    def test_fetch_unknown_provider_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--provider", "madeup"],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"


class TestDataRefresh:
    def test_refresh_nifty50_reports_all_tickers(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nifty10",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok"
        assert data["universe"] == "nifty10"
        assert len(data["symbols"]) == 10
        assert all(s["rows"] > 0 for s in data["symbols"])

    def test_refresh_unknown_universe_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nope50",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"

    def test_refresh_reports_force_flag(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nifty10",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--force"],
        )
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["force"] is True


