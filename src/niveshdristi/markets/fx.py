"""FX / base-currency groundwork (NEW, P9-S5) — a TYPED STUB ONLY.

Groundwork for multi-market NAV: the types and the refusal semantics
exist; NO rates, NO feed, NO invented numbers. Placed in the MARKETS layer
(not the neutral zone) because currency conversion is market composition,
not engine logic — core/ and engine/ stay untouched and remain
single-currency; a multi-market NAV would compose conversion here.

Every FxRate REQUIRES a non-empty source and an as-of date (mirrors the
verified-true rule for cost schedules)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict

from niveshdristi.core.errors import ConfigurationError


class FxRateUnavailable(ConfigurationError):
    """No FxRate was supplied for a required pair/date — conversion
    REFUSES rather than inventing or defaulting."""


class FxRate(BaseModel):
    """One explicit FX rate, with provenance. REQUIRES source + as_of."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    rate: float = Field(gt=0)
    source: str = Field(min_length=1)
    as_of: date

    @model_validator(mode="after")
    def _distinct_currencies(self) -> "FxRate":
        if self.base_currency == self.quote_currency:
            raise ValueError("base and quote currencies must differ")
        return self


class BaseCurrency(BaseModel):
    """The reporting currency of a book/fund (multi-market NAV target)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    currency: str = Field(min_length=3, max_length=3)


class FxConverter:
    """Converts amounts between currencies using ONLY explicitly supplied
    FxRate objects. With no rate for a pair/date it raises
    FxRateUnavailable — never invents, never defaults to 1.0."""

    def __init__(self, rates: tuple[FxRate, ...] = ()) -> None:
        self._rates: dict[tuple[str, str, date], FxRate] = {}
        for rate in rates:
            self._rates[(rate.base_currency, rate.quote_currency,
                         rate.as_of)] = rate

    def convert(self, amount: float, from_currency: str, to_currency: str,
                *, as_of: date) -> float:
        """amount expressed in from_currency -> to_currency at as_of."""
        if from_currency == to_currency:
            return amount
        rate = self._rates.get((from_currency, to_currency, as_of))
        if rate is None:
            raise FxRateUnavailable(
                f"no FX rate supplied for {from_currency}->{to_currency} "
                f"on {as_of.isoformat()}; multi-market NAV is GROUNDWORK "
                "ONLY — supply an explicit FxRate(source=..., as_of=...)"
            )
        return amount * rate.rate
