"""Portfolio construction: conviction -> target weights (NEW, Phase 4).

Pure function of its inputs — no clock, no I/O, no look-ahead surface (the
no-look-ahead property test is NOT APPLICABLE by construction: nothing is
fetched here; everything arrives as arguments).

Rules applied, in order:
1. conviction-weighted target weights across the given signals;
2. LONG-ONLY clamp when MarketRules.shorting_allowed is False (negative
   convictions contribute zero weight — they are dropped, not netted);
3. optional inverse-volatility scaling when per-symbol vols are supplied
   (weight divided by vol, then renormalised);
4. total weight capped at 1.0 — any excess remains as cash.

Conviction scales across models are NOT calibrated (see alpha/registry);
these weights are a deterministic mapping, not a probability allocation.
Amounts are unitless floats; no market literals here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from niveshdristi.core.market_rules import MarketRules
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
MAX_TOTAL_WEIGHT = 1.0  # remainder stays in cash
MIN_VOL = 1e-06  # floor to avoid division by zero in inverse-vol scaling


def construct_targets(
    signals: Sequence[Signal],
    rules: MarketRules,
    vols: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Conviction-weighted target weights, long-only per market rules.

    Args:
        signals: Signals for one assessment date (one per instrument).
        rules: Neutral market rules (shorting_allowed drives the clamp).
        vols: Optional per-symbol realised volatilities for inverse-vol
            scaling (supplied by the caller, never looked up here).

    Returns:
        symbol -> target weight in [0, 1]; weights sum to at most 1.0.
    """
    long_only = not rules.shorting_allowed
    by_symbol: dict[str, float] = {}
    for s in signals:
        conviction = s.effective_conviction(long_only=long_only)
        if long_only and conviction <= 0.0:
            continue  # dropped under long-only; no negative weights netted
        if conviction == 0.0:
            continue  # zero conviction is never a position
        by_symbol[s.instrument.symbol] = conviction

    if not by_symbol:
        return {}  # all-cash when every conviction is non-positive

    if vols is not None:
        scaled = {
            sym: w / max(vols.get(sym, MIN_VOL), MIN_VOL) for sym, w in by_symbol.items()
        }
        total = sum(scaled.values())
        if total > 0:
            by_symbol = scaled

    total = sum(by_symbol.values())
    if total <= 0:
        if rules.shorting_allowed and by_symbol:
            # Zero/negative-gross book cannot be normalised by net exposure;
            # return the raw conviction-scaled weights (sum <= 0), documented.
            return dict(by_symbol)
        return {}
    weights = {sym: w / total for sym, w in by_symbol.items()}

    # Cap total at MAX_TOTAL_WEIGHT (remainder = cash). Proportionally scaled.
    current_total = sum(weights.values())
    if current_total > MAX_TOTAL_WEIGHT:
        factor = MAX_TOTAL_WEIGHT / current_total
        weights = {sym: w * factor for sym, w in weights.items()}
    return weights
