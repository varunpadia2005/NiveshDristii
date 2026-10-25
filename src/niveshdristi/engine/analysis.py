"""Benchmark comparison and regime breakdown (NEW, Phase 5).

Benchmark consumed as a frame BY ROLE (no symbol literals). All statistics
are simple documented regressions/arithmetic — no new dependencies.

- benchmark_not_tri is ALWAYS added unless the caller supplies
  tri_asserted=True WITH a non-empty source string (then the source is
  recorded in the result).
- With no benchmark frame, comparison returns typed "unavailable", never
  zero.
- Regime breakdown: sessions labelled by trailing benchmark realized
  volatility and trend using UNVALIDATED DEFAULT thresholds (a proxy —
  limitation regime_vol_proxy). Regimes below min_sessions report
  "insufficient data".
"""

from __future__ import annotations

import math
from datetime import date

import polars as pl
from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.limitations import DataLimitations

# UNVALIDATED DEFAULTS (proxy thresholds; hypotheses, not calibrated)
VOL_WINDOW = 20
VOL_HIGH = 0.20  # annualized trailing vol at/above which regime is "high_vol"
TREND_WINDOW = 60
TREND_THRESHOLD = 0.10  # |trailing return| at/above this = trending
MIN_SESSIONS_PER_REGIME = 10


class BenchmarkComparison(BaseModel):
    """Benchmark comparison outcome; 'unavailable' is typed, never zero."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    excess_return: float | None = None
    beta: float | None = None
    alpha: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    source: str | None = None  # TRI source when asserted
    unavailable_reason: str | None = None


class RegimeStats(BaseModel):
    """Per-regime metrics; below min_sessions -> insufficient data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    regime: str
    sessions: int
    annualized_return: float | None = None  # None = insufficient data
    annualized_vol: float | None = None
    average_exposure: float | None = None


class RegimeBreakdown(BaseModel):
    """Regime-labelled metrics; carries the proxy limitation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitations: DataLimitations  # REQUIRED (regime_vol_proxy included)
    regimes: tuple[RegimeStats, ...]

    @property
    def banner(self) -> str | None:
        return self.limitations.banner


def _align_daily(
    strategy_curve: tuple[tuple[date, float], ...],
    benchmark_frame: pl.DataFrame,
) -> tuple[list[float], list[float]]:
    """Daily returns of strategy and benchmark on COMMON dates."""
    bench = {
        str(d)[:10]: float(v)
        for d, v in zip(
            benchmark_frame["date"].to_list(),
            benchmark_frame["close"].to_list(),
            strict=True,
        )
    }
    strat_rets: list[float] = []
    bench_rets: list[float] = []
    for i in range(1, len(strategy_curve)):
        prev_day, prev_val = strategy_curve[i - 1]
        day, val = strategy_curve[i]
        key = day.isoformat()
        prev_key = prev_day.isoformat()
        if key not in bench or prev_key not in bench:
            continue
        strat_rets.append(val / prev_val - 1.0)
        bench_rets.append(bench[key] / bench[prev_key] - 1.0)
    return strat_rets, bench_rets


def compare_to_benchmark(
    strategy_curve: tuple[tuple[date, float], ...],
    benchmark_frame: pl.DataFrame,
    *,
    tri_asserted: bool = False,
    tri_source: str = "",
) -> tuple[BenchmarkComparison, DataLimitations]:
    """Excess return, beta, alpha (simple regression), TE, IR (NEW)."""
    codes = {"benchmark_not_tri"} if not (tri_asserted and tri_source.strip()) else set()
    if not benchmark_frame.height:
        return (
            BenchmarkComparison(
                available=False, source=tri_source or None,
                unavailable_reason="no benchmark frame supplied",
            ),
            DataLimitations(CODES=frozenset(codes)),
        )
    strat, bench = _align_daily(strategy_curve, benchmark_frame)
    if len(strat) < 2:
        return (
            BenchmarkComparison(
                available=False, source=tri_source or None,
                unavailable_reason="fewer than 2 aligned sessions",
            ),
            DataLimitations(CODES=frozenset(codes)),
        )
    mean_s = sum(strat) / len(strat)
    mean_b = sum(bench) / len(bench)
    cov = sum(
        (s - mean_s) * (b - mean_b) for s, b in zip(strat, bench, strict=True)
    ) / (len(strat) - 1)
    var_b = sum((b - mean_b) ** 2 for b in bench) / (len(bench) - 1)
    if var_b == 0:
        return (
            BenchmarkComparison(
                available=False, source=tri_source or None,
                unavailable_reason="benchmark has zero variance",
            ),
            DataLimitations(CODES=frozenset(codes)),
        )
    beta = cov / var_b
    alpha_annual = (mean_s - mean_b) * 252  # simple annualized intercept proxy
    te = math.sqrt(
        sum(((s - b) - (mean_s - mean_b)) ** 2 for s, b in zip(strat, bench, strict=True))
        / (len(strat) - 1)
    )
    active = mean_s - mean_b
    ir = (active * 252) / (te * math.sqrt(252)) if te > 0 else 0.0
    return (
        BenchmarkComparison(
            available=True,
            excess_return=active * 252,
            beta=round(beta, 6),
            alpha=round(alpha_annual, 6),
            tracking_error=round(te * math.sqrt(252), 6),
            information_ratio=round(ir, 6),
            source=tri_source or None,
        ),
        DataLimitations(CODES=frozenset(codes)),
    )


def label_regimes(benchmark_frame: pl.DataFrame) -> dict[str, str]:
    """Session date -> regime label (proxy: trend + trailing vol)."""
    rows = sorted(
        zip(
            [str(d)[:10] for d in benchmark_frame["date"].to_list()],
            [float(v) for v in benchmark_frame["close"].to_list()],
            strict=True,
        )
    )
    labels: dict[str, str] = {}
    closes = [(d, v) for d, v in rows]
    for i, (day, value) in enumerate(closes):
        # trailing trend over TREND_WINDOW
        if i < TREND_WINDOW:
            labels[day] = "insufficient_history"
            continue
        ret = value / closes[i - TREND_WINDOW][1] - 1.0
        # trailing vol over VOL_WINDOW
        window = [closes[j][1] for j in range(i - VOL_WINDOW, i)]
        rets = [window[k] / window[k - 1] - 1.0 for k in range(1, len(window))]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        vol = math.sqrt(var) * math.sqrt(252) if var > 0 else 0.0
        if vol >= VOL_HIGH:
            labels[day] = "high_vol"
        elif ret >= TREND_THRESHOLD:
            labels[day] = "trend_up"
        elif ret <= -TREND_THRESHOLD:
            labels[day] = "trend_down"
        else:
            labels[day] = "choppy"
    return labels


def regime_breakdown(
    strategy_curve: tuple[tuple[date, float], ...],
    benchmark_frame: pl.DataFrame,
    exposure_by_session: list[float],
) -> RegimeBreakdown:
    """Metrics per regime; below MIN_SESSIONS_PER_REGIME -> None values."""
    labels = label_regimes(benchmark_frame)
    curve_by_day = {d.isoformat(): v for d, v in strategy_curve}
    groups: dict[str, list[float]] = {}
    exposures: dict[str, list[float]] = {}
    ordered_days = [d.isoformat() for d, _ in strategy_curve]
    for i, day in enumerate(ordered_days[1:], start=1):
        prev = ordered_days[i - 1]
        if day not in labels or prev not in labels:
            continue
        if curve_by_day[prev] <= 0:
            continue
        regime = labels[day]
        ret = curve_by_day[day] / curve_by_day[prev] - 1.0
        groups.setdefault(regime, []).append(ret)
        exposures.setdefault(regime, []).append(
            exposure_by_session[i - 1] if i - 1 < len(exposure_by_session) else 0.0
        )
    stats: list[RegimeStats] = []
    for regime in sorted(groups):
        rets = groups[regime]
        n = len(rets)
        if n < MIN_SESSIONS_PER_REGIME:
            stats.append(RegimeStats(regime=regime, sessions=n))
            continue
        mean = sum(rets) / n
        ann_ret = (1.0 + mean) ** 252 - 1.0 if mean > -1 else -1.0
        var = sum((r - mean) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
        ann_vol = math.sqrt(var) * math.sqrt(252)
        avg_exp = sum(exposures[regime]) / n
        stats.append(
            RegimeStats(
                regime=regime, sessions=n,
                annualized_return=round(ann_ret, 6),
                annualized_vol=round(ann_vol, 6),
                average_exposure=round(avg_exp, 6),
            )
        )
    return RegimeBreakdown(
        limitations=DataLimitations(CODES=frozenset({"regime_vol_proxy"})),
        regimes=tuple(stats),
    )
