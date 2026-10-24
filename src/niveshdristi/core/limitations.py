"""Data-limitations contract (NEW, Phase 5) — neutral, frozen.

Every backtest/validation result object must carry a DataLimitations
instance; the constructor of any such result type is expected to REQUIRE it
(convention enforced by tests: a result-like container without it cannot be
built). Analogous to rates_verified: the banner cannot be dropped while any
limitation is present, and `promotable` is False until the set is empty.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator
from pydantic.config import ConfigDict


class DataLimitations(BaseModel):
    """Frozen set of limitation codes + generated banner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Initial catalogue of limitation codes (documented meanings):
    #   survivorship_universe        — universe lacks delisted names
    #   approximate_universe         — current-state membership, not as-of
    #   derived_calendar             — calendar derived from price data
    #   adjusted_price_basis         — prices embed future corporate actions
    #   raw_price_basis              — raw prices; split handling absent
    #   corporate_actions_unavailable — no corporate-action source
    #   rates_unverified             — cost/tax rates all # VERIFY
    #   no_pit_fundamentals          — no announcement-dated fundamentals
    #   benchmark_not_tri            — benchmark is not a total-return index
    #   regime_vol_proxy             — volatility index is a proxy/fixture
    CODES: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _codes_known(self) -> DataLimitations:
        from niveshdristi.core.errors import ConfigurationError

        allowed = {
            "survivorship_universe",
            "approximate_universe",
            "derived_calendar",
            "adjusted_price_basis",
            "raw_price_basis",
            "corporate_actions_unavailable",
            "rates_unverified",
            "no_pit_fundamentals",
            "benchmark_not_tri",
            "regime_vol_proxy",
        }
        unknown = sorted(self.CODES - allowed)
        if unknown:
            raise ConfigurationError(f"unknown limitation codes: {unknown}")
        return self

    @property
    def banner(self) -> str | None:
        """Human-readable banner; None only when no limitation is present."""
        if not self.CODES:
            return None
        codes = ", ".join(sorted(self.CODES))
        return f"DATA LIMITATIONS: {codes}"

    @property
    def promotable(self) -> bool:
        """False whenever ANY limitation is present."""
        return not self.CODES
