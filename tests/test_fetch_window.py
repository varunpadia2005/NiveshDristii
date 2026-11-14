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

from datetime import date

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
