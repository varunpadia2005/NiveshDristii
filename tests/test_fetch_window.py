"""P11-S5: the live-fetch window defect, proven OFFLINE.

Suspected defect (audit finding): cli/main.py::_paper_fetch_bars passed
`start` as BOTH start and end to YFinanceClient._fetch — yfinance's end
is EXCLUSIVE, so the window [start, start) is empty (or one row). The
fact "yfinance end is exclusive" is supplied by the Phase 11-A step
spec; this test encodes it in a recording fake client and asserts the
fetch receives start < end and returns rows > 0.

The fake patches the ADAPTER CLASS (one level below _paper_fetch_bars),
so the existing _paper_fetch_bars-level provider fakes are untouched.
No network: the fake client never imports yfinance.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from niveshdristi.cli.main import _paper_fetch_bars

ADAPTER = "niveshdristi.markets.in_nse.providers.yfinance_adapter.YFinanceClient"


class _RecordingClient:
    """End-EXCLUSIVE fake: returns one OHLCV row per day in [start, end)
    and records every (start, end) argument it receives."""

    calls: list[tuple[date, date]] = []

    def _fetch(self, provider_symbol, start, end, auto_adjust):
        _RecordingClient.calls.append((start, end))
        days = pd.date_range(start, end, freq="D", inclusive="left")
        return pd.DataFrame(
            {
                "Open": [100.0] * len(days),
                "High": [101.0] * len(days),
                "Low": [99.0] * len(days),
                "Close": [100.0] * len(days),
                "Volume": [1_000_000] * len(days),
            },
            index=pd.DatetimeIndex(days, name="Date"),
        )


@pytest.fixture
def recording_client(monkeypatch):
    _RecordingClient.calls = []
    monkeypatch.setattr(ADAPTER, _RecordingClient)
    return _RecordingClient


class TestFetchWindowP11:
    def test_fetch_receives_start_before_end_and_returns_rows(
        self, recording_client
    ):
        """The CLI fetch window must be [start_window, candidate): the
        adapter must receive start < end and the frames must carry rows
        (the [start, start) window is EMPTY under end-exclusive
        semantics — the defect this test pins)."""
        start_window = date(2026, 9, 1)
        candidate = date(2026, 9, 30)
        frames = _paper_fetch_bars(["SYN090"], start_window, candidate)
        assert recording_client.calls, "the adapter must have been called"
        for start, end in recording_client.calls:
            assert start < end, (
                f"_fetch received start == end ({start}); the "
                "end-exclusive window is EMPTY — the fetch window is "
                "defective"
            )
        for symbol, frame in frames.items():
            assert frame.height > 0, (
                f"{symbol}: the fetched window has ZERO rows under "
                "end-exclusive semantics"
            )

    def test_window_covers_the_derived_history(self, recording_client):
        """The end must be the candidate (clock_now), not the window
        start: the fetched span covers the required history days."""
        candidate = date(2026, 9, 30)
        _paper_fetch_bars(["SYN090"], date(2026, 9, 1), candidate)
        assert recording_client.calls, "the adapter must have been called"
        for start, end in recording_client.calls:
            assert (end - start).days >= 20, (
                f"fetch span {(end - start).days} days is too short for "
                "the derived history window"
            )


class TestPaperFetchBarsUnnamedIndex:
    def test_unnamed_datetime_index_becomes_date_column(self, tmp_path):
        """P13-A #2: _paper_fetch_bars lowercases reset_index() columns but
        an UNNAMED DatetimeIndex becomes 'index', not 'date' — the fund
        then halts with 'unable to find column date'. The first column
        must be renamed to 'date' (same convention as the marketdata
        adapter's _to_polars)."""
        import pandas as pd

        from niveshdristi.cli.main import _paper_fetch_bars

        class _UnnamedIndexProvider:
            def _fetch(self, provider_symbol, start, end, auto_adjust):
                idx = pd.date_range(start, end - timedelta(days=1), freq="D")
                return pd.DataFrame(
                    {"Open": [100.0] * len(idx), "High": [101.0] * len(idx),
                     "Low": [99.0] * len(idx), "Close": [100.5] * len(idx),
                     "Volume": [1_000_000] * len(idx)},
                    index=pd.DatetimeIndex(idx),  # UNNAMED index
                )

        import niveshdristi.markets.in_nse.providers.yfinance_adapter as yfa
        original = yfa.YFinanceClient._fetch
        yfa.YFinanceClient._fetch = _UnnamedIndexProvider._fetch
        try:
            start = date(2026, 9, 1)
            end = date(2026, 9, 20)
            frames = _paper_fetch_bars(["SYN090"], start, end)
        finally:
            yfa.YFinanceClient._fetch = original
        frame = frames["SYN090"]
        assert "date" in frame.columns, (
            "the frame must carry a 'date' column — an unnamed "
            "DatetimeIndex must be renamed, not lowercased to 'index'"
        )
        assert frame.height > 0
