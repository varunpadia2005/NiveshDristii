"""P9-S5: FX groundwork — typed stub, provenance-required rates, refusal
semantics. NO real rate exists anywhere (test literals only)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from niveshdristi.markets.fx import (
    BaseCurrency,
    FxConverter,
    FxRate,
    FxRateUnavailable,
)


def _rate(**over):
    base = {
        "base_currency": "INR", "quote_currency": "USD", "rate": 0.011,
        "source": "test-source", "as_of": date(2026, 11, 1),
    }
    base.update(over)
    return FxRate(**base)


class TestFxGroundwork:
    def test_rate_requires_source_and_as_of(self):
        with pytest.raises(ValidationError, match="source"):
            _rate(source="")
        with pytest.raises(ValidationError, match="as_of"):
            FxRate(base_currency="INR", quote_currency="USD", rate=0.011,
                   source="s")  # no as_of

    def test_distinct_currencies(self):
        with pytest.raises(ValidationError, match="differ"):
            _rate(base_currency="USD", quote_currency="USD")

    def test_same_currency_passthrough(self):
        conv = FxConverter()
        assert conv.convert(100.0, "USD", "USD", as_of=date(2026, 11, 1)) == 100.0

    def test_refusal_without_rate_is_typed(self):
        conv = FxConverter()
        with pytest.raises(FxRateUnavailable, match="GROUNDWORK"):
            conv.convert(100.0, "USD", "EUR", as_of=date(2026, 11, 1))

    def test_no_rate_for_that_date_refuses(self):
        conv = FxConverter((_rate(as_of=date(2026, 1, 1)),))
        with pytest.raises(FxRateUnavailable, match="2026-11-01"):
            conv.convert(100.0, "INR", "USD", as_of=date(2026, 11, 1))

    def test_explicit_rate_converts(self):
        conv = FxConverter((_rate(),))
        assert conv.convert(100.0, "INR", "USD",
                            as_of=date(2026, 11, 1)) == pytest.approx(1.1)
        # hand-derived: 100 INR x 0.011 = 1.10 USD

    def test_base_currency_type(self):
        bc = BaseCurrency(currency="USD")
        assert bc.currency == "USD"
        with pytest.raises(ValidationError, match="string_too_long"):
            BaseCurrency(currency="usdollars")
