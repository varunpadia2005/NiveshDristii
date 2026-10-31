"""Deterministic risk gates (NEW, Phase 4) — plain Python, no I/O, no clock.

Design rules honored: every input is explicit (targets, current weights,
MarketRules, GateLimits, prices, ADV, caps, NAV, sector map, equity history,
decision date). Nothing is looked up inside a gate. The chain is MONOTONE: a
gate may only reduce a weight or remove a symbol, never increase one.

GatedTargets can only be created by run_chain via a module-private
construction token — a CONVENTION CHECK (documented), not a security
boundary: Python cannot enforce true privacy.

S1 PROPERTY (documented, tested): construct_targets always sums positive
convictions to 1.0 — conviction fixes RELATIVE size only, never the cash
level. The gates (max position, min cash, drawdown) are what create cash:
e.g. a single 0.01 conviction becomes weight 1.0 before gates, then the
max-position gate clips it.

Constants are UNVALIDATED DEFAULTS. Neutral zone: no market literals, no
currency symbols; amounts are unitless floats.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from niveshdristi.core.errors import RiskGateError
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.core.signal import Signal  # noqa: F401  (S1 property doc reference)

# UNVALIDATED DEFAULTS (hypotheses, not calibrated)
DEFAULT_EXCLUSION_STALENESS_WARN_DAYS = 90  # age beyond this adds a warning only


class _ConstructionToken:
    """Module-private marker; only run_chain holds the instance."""


_TOKEN = _ConstructionToken()


class GateLimits(BaseModel):
    """Neutral limits (the caller converts from its Mandate/source).

    All fractions are of NAV; all amounts are plain currency floats.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_position_pct: float = Field(default=0.10, ge=0)
    max_sector_pct: float = Field(default=0.30, ge=0)
    max_positions: int = Field(default=20, ge=1)
    min_cash_pct: float = Field(default=0.05, ge=0)
    adv_fraction: float = Field(default=0.05, ge=0)  # position value <= this x ADV
    turnover_max: float = Field(default=0.30, ge=0)  # turnover as fraction of NAV
    min_market_cap: float = Field(default=0.0, ge=0)  # inert without cap data
    drawdown_threshold: float = Field(default=0.20, ge=0)  # fraction from peak
    drawdown_exposure_factor: float = Field(default=0.50, ge=0)
    exclusion_staleness_warn_days: int = Field(
        default=DEFAULT_EXCLUSION_STALENESS_WARN_DAYS, ge=0
    )


class GateLog(BaseModel):
    """One gate outcome entry (frozen)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: str
    symbol: str | None = None  # None = portfolio-level
    weight_before: float | None = None
    weight_after: float | None = None
    limit: float | None = None
    outcome: str  # "clamped" | "removed" | "info" | "skipped: no data"
    reason: str


class GatedTargets(BaseModel):
    """Output of run_chain only (construction token convention check)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weights: dict[str, float]
    log: tuple[GateLog, ...]

    def __init__(self, _token: Any = None, **data: Any) -> None:
        if _token is not _TOKEN:
            raise RiskGateError(
                "GatedTargets must be created via run_chain (construction token)"
            )
        super().__init__(**data)

    @classmethod
    def _deserialize(cls, data: dict[str, Any]) -> GatedTargets:
        """Module-private deserialization (ledger cache round trip); the
        direct-construction convention check still applies to callers."""
        return cls(_token=_TOKEN, **data)


def _remove_empty(weights: dict[str, float]) -> None:
    for sym in [s for s, w in weights.items() if w <= 0.0]:
        del weights[sym]


def run_chain(
    targets: Mapping[str, float],
    *,
    limits: GateLimits,
    rules: MarketRules,
    current_weights: Mapping[str, float],
    prices: Mapping[str, float],
    advs: Mapping[str, float] | None = None,
    market_caps: Mapping[str, float] | None = None,
    sector_map: Mapping[str, str] | None = None,
    nav: float = 1_000_000.0,
    equity_history: tuple[float, ...] | list[float] | None = None,
    decision_date: date | None = None,
) -> GatedTargets:
    """Apply the gate chain; returns GatedTargets with weights and full log.

    Gate order: exclusions, min price, min market cap (inert without data),
    max positions, max position %, max sector %, ADV cap, turnover cap,
    min cash, drawdown circuit; then a final validation pass that RAISES
    RiskGateError rather than returning a violating result.
    """
    weights: dict[str, float] = dict(targets)
    log: list[GateLog] = []

    def log_entry(**kwargs: Any) -> None:
        log.append(GateLog(**kwargs))

    # 1. Exclusion list (staleness adds a WARNING to the reason only)
    excl = rules.exclusions
    age_days: int | None = None
    if excl.as_of is not None and decision_date is not None:
        age_days = (decision_date - excl.as_of).days
    stale = age_days is not None and age_days > limits.exclusion_staleness_warn_days
    for sym in list(weights):
        if sym in excl.symbols:
            before = weights.pop(sym)
            reason = (
                f"excluded by list source={excl.source!r} as_of={excl.as_of} "
                f"age_days={age_days}"
            )
            if stale:
                reason += (
                    f" WARNING: list older than {limits.exclusion_staleness_warn_days}d"
                    " (UNVALIDATED DEFAULT threshold; warning only)"
                )
            log_entry(
                gate="exclusion",
                symbol=sym,
                weight_before=before,
                weight_after=0.0,
                outcome="removed",
                reason=reason,
            )

    # 2. Min price
    for sym in list(weights):
        price = prices.get(sym)
        if price is None:
            log_entry(
                gate="min_price",
                symbol=sym,
                outcome="skipped: no data",
                reason="no price supplied",
            )
            continue
        if price < rules.min_price:
            before = weights.pop(sym)
            log_entry(
                gate="min_price",
                symbol=sym,
                weight_before=before,
                weight_after=0.0,
                limit=rules.min_price,
                outcome="removed",
                reason=f"price {price} below min {rules.min_price}",
            )

    # 3. Min market cap — inert unless cap data is supplied
    if market_caps is None:
        log_entry(
            gate="min_market_cap",
            outcome="skipped: no data",
            reason="no market-cap data supplied; gate inert",
        )
    else:
        for sym in list(weights):
            cap = market_caps.get(sym)
            if cap is None:
                continue
            if cap < limits.min_market_cap:
                before = weights.pop(sym)
                log_entry(
                    gate="min_market_cap",
                    symbol=sym,
                    weight_before=before,
                    weight_after=0.0,
                    limit=limits.min_market_cap,
                    outcome="removed",
                    reason=f"cap {cap} below min {limits.min_market_cap}",
                )

    # 4. Max positions — keep the top-N by weight (deterministic tie-break)
    if len(weights) > limits.max_positions:
        ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
        for sym, w in ranked[limits.max_positions:]:
            del weights[sym]
            log_entry(
                gate="max_positions",
                symbol=sym,
                weight_before=w,
                weight_after=0.0,
                limit=float(limits.max_positions),
                outcome="removed",
                reason=f"positions beyond limit {limits.max_positions}",
            )

    # 5. Max position %
    for sym in list(weights):
        if weights[sym] > limits.max_position_pct:
            before = weights[sym]
            weights[sym] = limits.max_position_pct
            log_entry(
                gate="max_position",
                symbol=sym,
                weight_before=before,
                weight_after=limits.max_position_pct,
                limit=limits.max_position_pct,
                outcome="clamped",
                reason=f"weight {before:.4f} above max {limits.max_position_pct}",
            )
    _remove_empty(weights)

    # 6. Max sector %
    if sector_map is not None:
        sectors: dict[str, float] = {}
        for sym, w in weights.items():
            sectors[sector_map.get(sym, "")] = sectors.get(sector_map.get(sym, ""), 0.0) + w
        for sector, total in sorted(sectors.items()):
            if total > limits.max_sector_pct:
                factor = limits.max_sector_pct / total
                for sym in list(weights):
                    if sector_map.get(sym, "") == sector:
                        before = weights[sym]
                        weights[sym] = before * factor
                        log_entry(
                            gate="max_sector",
                            symbol=sym,
                            weight_before=before,
                            weight_after=weights[sym],
                            limit=limits.max_sector_pct,
                            outcome="clamped",
                            reason=f"sector {sector!r} total {total:.4f} above max",
                        )
    _remove_empty(weights)

    # 7. ADV / liquidity cap
    if advs is None:
        log_entry(
            gate="adv_cap",
            outcome="skipped: no data",
            reason="no ADV data supplied; gate inert",
        )
    else:
        for sym in list(weights):
            adv = advs.get(sym)
            if adv is None:
                continue
            max_value = limits.adv_fraction * adv
            current_value = weights[sym] * nav
            if current_value > max_value and max_value >= 0:
                before = weights[sym]
                weights[sym] = max_value / nav if nav > 0 else 0.0
                log_entry(
                    gate="adv_cap",
                    symbol=sym,
                    weight_before=before,
                    weight_after=weights[sym],
                    limit=limits.adv_fraction,
                    outcome="clamped",
                    reason=(
                        f"position value {current_value:.0f} exceeds "
                        f"{limits.adv_fraction} x ADV {adv:.0f}"
                    ),
                )
        _remove_empty(weights)

    # 8. Turnover cap (monotone: only shrinks increases toward current)
    all_symbols = set(weights) | set(current_weights)
    turnover = sum(
        abs(weights.get(s, 0.0) - current_weights.get(s, 0.0)) for s in all_symbols
    )
    if turnover > limits.turnover_max:
        increases = {
            s: weights.get(s, 0.0) - current_weights.get(s, 0.0)
            for s in weights
            if weights.get(s, 0.0) > current_weights.get(s, 0.0)
        }
        total_increase = sum(increases.values())
        excess = turnover - limits.turnover_max
        if total_increase > 0 and excess > 0:
            factor = max(0.0, 1.0 - excess / total_increase)
            for sym in list(weights):
                cur = current_weights.get(sym, 0.0)
                tgt = weights[sym]
                if tgt > cur:
                    weights[sym] = cur + (tgt - cur) * factor
            log_entry(
                gate="turnover",
                outcome="clamped",
                weight_before=turnover,
                weight_after=min(turnover, limits.turnover_max),
                limit=limits.turnover_max,
                reason=f"turnover {turnover:.4f} above cap; increases scaled",
            )
        _remove_empty(weights)

    # 9. Min cash
    exposure = sum(weights.values())
    cash = 1.0 - exposure
    if cash < limits.min_cash_pct:
        allowed = 1.0 - limits.min_cash_pct
        if exposure > 0:
            factor = allowed / exposure
            for sym in list(weights):
                before = weights[sym]
                weights[sym] = before * factor
            log_entry(
                gate="min_cash",
                outcome="clamped",
                weight_before=exposure,
                weight_after=allowed,
                limit=limits.min_cash_pct,
                reason=f"cash {cash:.4f} below min {limits.min_cash_pct}",
            )
        _remove_empty(weights)

    # 10. Drawdown circuit (cap total exposure at the factor when triggered)
    if equity_history:
        peak = max(equity_history)
        last = equity_history[-1]
        drawdown = (peak - last) / peak if peak > 0 else 0.0
        if drawdown >= limits.drawdown_threshold:
            exposure = sum(weights.values())
            cap_exposure = limits.drawdown_exposure_factor
            if exposure > cap_exposure:
                factor = cap_exposure / exposure
                for sym in list(weights):
                    weights[sym] = weights[sym] * factor
                log_entry(
                    gate="drawdown_circuit",
                    outcome="clamped",
                    weight_before=exposure,
                    weight_after=cap_exposure,
                    limit=limits.drawdown_threshold,
                    reason=(
                        f"drawdown {drawdown:.4f} at/above threshold "
                        f"{limits.drawdown_threshold}; exposure capped at "
                        f"{cap_exposure}"
                    ),
                )
            else:
                log_entry(
                    gate="drawdown_circuit",
                    outcome="info",
                    limit=limits.drawdown_threshold,
                    reason=(
                        f"drawdown {drawdown:.4f} at/above threshold; exposure "
                        f"{exposure:.4f} already within cap"
                    ),
                )
        _remove_empty(weights)

    # Final validation pass: every limit must hold, else a typed error.
    exposure = sum(weights.values())
    errors: list[str] = []
    if len(weights) > limits.max_positions:
        errors.append(f"positions {len(weights)} > {limits.max_positions}")
    for sym, w in weights.items():
        if w > limits.max_position_pct + 1e-12:
            errors.append(f"{sym} weight {w} > max_position_pct")
        if w > dict(targets).get(sym, 0.0) + 1e-12:
            errors.append(f"{sym} weight {w} increased above input (monotonicity)")
    if sector_map is not None:
        agg: dict[str, float] = {}
        for sym, w in weights.items():
            key = sector_map.get(sym, "")
            agg[key] = agg.get(key, 0.0) + w
        for sector, total in agg.items():
            if total > limits.max_sector_pct + 1e-12:
                errors.append(f"sector {sector} total {total} > max_sector_pct")
    if 1.0 - exposure < limits.min_cash_pct - 1e-12:
        errors.append(f"cash {1.0 - exposure} < min_cash_pct")
    if advs is not None:
        for sym, w in weights.items():
            adv = advs.get(sym)
            if adv is not None and w * nav > limits.adv_fraction * adv + 1e-6:
                errors.append(f"{sym} violates ADV cap")
    if errors:
        raise RiskGateError(f"gate chain validation failed: {errors}")

    return GatedTargets(_token=_TOKEN, weights=weights, log=tuple(log))
