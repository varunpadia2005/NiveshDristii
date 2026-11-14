"""Shared helpers for the F1 long-only guard tests (NEW)."""

from __future__ import annotations

from datetime import UTC, datetime


def make_signal(symbol: str, conviction: float):
    """A real frozen Signal (effective_conviction clamps under long-only)."""
    from niveshdristi.core.instrument import Instrument
    from niveshdristi.core.signal import Signal

    return Signal(
        instrument=Instrument(
            symbol=symbol, exchange="TEST_M", market_id="TEST_M", currency="XXX"
        ),
        as_of=datetime(2026, 11, 1, 15, 0, tzinfo=UTC),
        conviction=conviction,
        horizon_days=10,
        thesis="Hypothesis: synthetic test signal.",
        evidence={"conviction": conviction},
        model_id="test_model",
    )


class DuckSignal:
    """Duck-typed signal whose effective_conviction does NOT clamp —
    exercises the construction-layer drop independently of core Signal."""

    def __init__(self, symbol: str, conviction: float) -> None:
        self.instrument_symbol = symbol
        self._conv = conviction

    @property
    def instrument(self):  # minimal structural attribute
        from niveshdristi.core.instrument import Instrument

        return Instrument(
            symbol=self.instrument_symbol, exchange="TEST_M",
            market_id="TEST_M", currency="XXX",
        )

    def effective_conviction(self, *, long_only: bool = True) -> float:
        return self._conv  # raw, never clamped
