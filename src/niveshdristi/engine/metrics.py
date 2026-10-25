"""Backtest metrics (NEW, Phase 5) — pure functions, documented conventions.

Conventions:
- CAGR: sessions/252 trading years, first to last net equity.
- Volatility: daily simple returns, SAMPLE std (ddof=1), x sqrt(252).
- Sharpe: (mean daily return - daily risk-free) / daily std x sqrt(252),
  with the risk-free supplied as an ANNUAL fraction (default 0.0).
- Sortino: (mean daily return - daily risk-free) / downside deviation,
  where downside deviation = sqrt(mean(min(r - rf_daily, 0)^2)) x sqrt(252)
  (documented: full-series downside deviation, not target-semivariance
  over positive-only observations).
- Max drawdown: peak-to-trough on the net equity curve, with dates.
- Turnover: annualized traded notional / (2 x average NAV).
- Hit rate: fraction of POSITIVE-return sessions among sessions WITH
  exposure (invested fraction > 0); flat sessions excluded by design.
- Cost drag: fees and slippage separately, in NAV bps.

Edge cases return a typed "unavailable" outcome (never a silent NaN):
fewer than 2 points, flat curve (zero std), zero equity.
"""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.limitations import DataLimitations

SESSIONS_PER_YEAR = 252


class Unavailable:
    """Typed unavailable outcome (mypy-visible, never a silent NaN)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover
        return f"Unavailable({self.reason!r})"


def _daily_returns(curve: tuple[tuple[date, float], ...]) -> list[float]:
    out = []
    for i in range(1, len(curve)):
        prev = curve[i - 1][1]
        if prev == 0:
            continue
        out.append(curve[i][1] / prev - 1.0)
    return out


def cagr(curve: tuple[tuple[date, float], ...]) -> float | Unavailable:
    """CAGR from first to last equity over sessions/252 years."""
    if len(curve) < 2:
        return Unavailable("fewer than 2 points")
    years = (len(curve) - 1) / SESSIONS_PER_YEAR
    first, last = curve[0][1], curve[-1][1]
    if first <= 0 or last <= 0:
        return Unavailable("non-positive equity")
    if years <= 0:
        return Unavailable("zero horizon")
    value: float = (last / first) ** (1.0 / years) - 1.0
    return value


def annualized_volatility(curve: tuple[tuple[date, float], ...]) -> float | Unavailable:
    returns = _daily_returns(curve)
    if len(returns) < 2:
        return Unavailable("fewer than 2 returns")
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    if var == 0:
        return Unavailable("flat curve: zero std")
    return math.sqrt(var) * math.sqrt(SESSIONS_PER_YEAR)


def sharpe(
    curve: tuple[tuple[date, float], ...], risk_free_annual: float = 0.0
) -> float | Unavailable:
    returns = _daily_returns(curve)
    if len(returns) < 2:
        return Unavailable("fewer than 2 returns")
    rf_daily = (1.0 + risk_free_annual) ** (1.0 / SESSIONS_PER_YEAR) - 1.0
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    if var == 0:
        return Unavailable("flat curve: zero std")
    value: float = mean / math.sqrt(var) * math.sqrt(SESSIONS_PER_YEAR)
    return value


def sortino(
    curve: tuple[tuple[date, float], ...], risk_free_annual: float = 0.0
) -> float | Unavailable:
    returns = _daily_returns(curve)
    if len(returns) < 2:
        return Unavailable("fewer than 2 returns")
    rf_daily = (1.0 + risk_free_annual) ** (1.0 / SESSIONS_PER_YEAR) - 1.0
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / len(excess)
    downside = math.sqrt(
        sum(min(x, 0.0) ** 2 for x in excess) / len(excess)
    )  # full-series downside deviation (documented)
    if downside == 0:
        return Unavailable("no downside observations")
    value: float = mean / downside * math.sqrt(SESSIONS_PER_YEAR)
    return value


def max_drawdown(curve: tuple[tuple[date, float], ...]):
    """(drawdown fraction, peak date, trough date) or Unavailable."""
    if len(curve) < 2:
        return Unavailable("fewer than 2 points")
    peak = curve[0]
    worst = (0.0, curve[0][0], curve[0][0])
    for day, value in curve:
        if value > peak[1]:
            peak = (day, value)
        if peak[1] > 0:
            dd = (peak[1] - value) / peak[1]
            if dd > worst[0]:
                worst = (dd, peak[0], day)
    if worst[0] == 0.0:
        return Unavailable("no drawdown")
    return worst


def turnover_annualized(
    traded_notional: float, sessions: int, average_nav: float
) -> float | Unavailable:
    """Annualized traded notional / (2 x average NAV)."""
    if sessions <= 0 or average_nav <= 0:
        return Unavailable("no sessions or non-positive NAV")
    return traded_notional / (2.0 * average_nav) * (SESSIONS_PER_YEAR / sessions)


def hit_rate(
    curve: tuple[tuple[date, float], ...], exposure_by_session: list[float]
) -> float | Unavailable:
    """Positive-return sessions / sessions WITH exposure (flat excluded)."""
    returns = _daily_returns(curve)
    # exposure_by_session aligns to curve[1:] (the return sessions)
    if len(returns) == 0 or len(exposure_by_session) != len(returns):
        return Unavailable("no returns or exposure misaligned")
    considered = [
        r for r, x in zip(returns, exposure_by_session, strict=True) if x > 0
    ]
    if not considered:
        return Unavailable("no sessions with exposure")
    return sum(1 for r in considered if r > 0) / len(considered)


def exposure_average(exposure_by_session: list[float]) -> float | Unavailable:
    if not exposure_by_session:
        return Unavailable("no sessions")
    return sum(exposure_by_session) / len(exposure_by_session)


class MetricsReport(BaseModel):
    """All metrics with their conventions; limitations required."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitations: DataLimitations  # REQUIRED
    rates_verified: bool
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    max_drawdown_peak: date | None = None
    max_drawdown_trough: date | None = None
    turnover: float | None
    hit_rate: float | None
    exposure: float | None
    cost_drag_fees_bps: float | None
    cost_drag_slippage_bps: float | None
    unavailable: dict[str, str] = {}
