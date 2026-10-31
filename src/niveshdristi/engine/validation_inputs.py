"""Validation inputs (NEW, Phase 5): TrialRecorder, walk-forward splits,
parameter sensitivity. PURE — no I/O, no clock, no randomness.

TrialRecorder: every backtest configuration evaluated is recorded with an
id, its parameters, its per-session net return series and its Sharpe.
ANYTHING that reports statistical significance takes the recorder as a
MANDATORY input; the number of trials is `len(recorder.trials)` — never
supplied by hand. A validation result built with zero recorded trials is an
error.

Walk-forward splits: deterministic; each split = [train_start, train_end)
train window, then a PURGE/EMBARGO gap of `embargo_sessions` sessions
(must be at least the longest model lookback — the models' rolling windows
mean session T's signal depends on data back to T-lookback, so train and
test information would overlap without the purge), then the test window;
step advances by the test window. Train always ends strictly before the
purge; test begins strictly after it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Any

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.core.limitations import DataLimitations

# UNVALIDATED DEFAULTS
DEFAULT_EMBARGO_SESSIONS = 60  # >= longest model lookback (200-session EMA would need 200)
DEFAULT_FRAGILITY_DROP = 0.30  # neighbor Sharpe drop beyond this = fragile


class Trial(BaseModel):
    """One evaluated backtest configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trial_id: str
    parameters: dict[str, str]  # stringly-typed for determinism
    net_returns: tuple[float, ...]
    sharpe: float


class TrialRecorder:
    """Append-only trial log; the source of truth for the trial count."""

    def __init__(self) -> None:
        self._trials: list[Trial] = []
        self._ids: set[str] = set()

    def record(
        self, trial_id: str, parameters: dict[str, Any], net_returns: Sequence[float]
    ) -> Trial:
        if trial_id in self._ids:
            raise ConfigurationError(f"duplicate trial_id: {trial_id!r}")
        returns = tuple(float(r) for r in net_returns)
        sharpe = _sharpe_of(returns)
        trial = Trial(
            trial_id=trial_id,
            parameters={k: str(v) for k, v in parameters.items()},
            net_returns=returns,
            sharpe=sharpe,
        )
        self._trials.append(trial)
        self._ids.add(trial_id)
        return trial

    @property
    def trials(self) -> tuple[Trial, ...]:
        return tuple(self._trials)

    @property
    def trial_count(self) -> int:
        return len(self._trials)

    def sharpe_variance(self) -> float:
        """Population variance of the recorded trial Sharpes."""
        n = len(self._trials)
        if n < 2:
            return 0.0
        sharpes = [t.sharpe for t in self._trials]
        mean = sum(sharpes) / n
        return sum((s - mean) ** 2 for s in sharpes) / n


def _sharpe_of(returns: tuple[float, ...]) -> float:
    """Annualized Sharpe of a net return series (rf=0; documented)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var == 0:
        return 0.0
    return mean / math.sqrt(var) * math.sqrt(252)


def walk_forward_splits(
    sessions: Sequence[date],
    *,
    train_sessions: int,
    test_sessions: int,
    embargo_sessions: int,
) -> list[tuple[int, int, int, int]]:
    """Deterministic walk-forward splits as (train_start, train_end_exclusive,
    test_start, test_end_exclusive) INDEX ranges.

    Invariant per split: train_end + embargo == test_start (train ends
    strictly before the purge gap; test begins strictly after it).
    """
    if train_sessions <= 0 or test_sessions <= 0 or embargo_sessions <= 0:
        raise ConfigurationError("train/test/embargo must all be positive")
    out: list[tuple[int, int, int, int]] = []
    start = 0
    while True:
        train_end = start + train_sessions
        test_start = train_end + embargo_sessions
        test_end = test_start + test_sessions
        if test_end > len(sessions):
            break
        out.append((start, train_end, test_start, test_end))
        start += test_sessions
    return out


def stitched_out_of_sample(
    sessions: Sequence[date],
    net_equity: Sequence[float],
    splits: Sequence[tuple[int, int, int, int]],
) -> tuple[float, ...]:
    """Out-of-sample net returns stitched in chronological order."""
    out: list[float] = []
    for _train_s, _train_e, test_s, test_e in splits:
        for i in range(test_s, test_e):
            if net_equity[i - 1] > 0 and net_equity[i] > 0:
                out.append(net_equity[i] / net_equity[i - 1] - 1.0)
    return tuple(out)


def parameter_sensitivity(
    grid: Sequence[tuple[str, dict[str, Any], tuple[float, ...]]],
    run_point: Any,
) -> tuple[tuple[tuple[str, Any, float, float], ...], list[str], DataLimitations]:
    """Evaluate a parameter grid; flags fragile neighbor points.

    run_point(param_name, param_value) -> (net_returns, fees, slippage):
    caller-supplied evaluator (each point RECORDED in the TrialRecorder by
    the caller before significance is reported).

    Returns ((param_name, value, sharpe, drag_bps), fragile_flags,
    limitations with rates_unverified).
    """
    points: list[tuple[str, Any, float, float]] = []
    for param_name, _base_params, values in grid:
        for value in values:
            net_returns, fees, slippage = run_point(param_name, value)
            trial = _sharpe_of(tuple(net_returns))
            drag_bps = ((fees + slippage) / 1_000_000.0) * 10_000 if net_returns else 0.0
            points.append((param_name, value, trial, drag_bps))
    fragile: list[str] = []
    for i in range(1, len(points)):
        name, value, sharpe, _drag = points[i]
        prev_name, prev_value, prev_sharpe, _prev_drag = points[i - 1]
        if name == prev_name and prev_sharpe > 0:
            drop = (prev_sharpe - sharpe) / prev_sharpe
            if drop > DEFAULT_FRAGILITY_DROP:
                fragile.append(
                    f"{name}={value}: Sharpe {prev_sharpe:.3f}->{sharpe:.3f} "
                    f"(-{drop:.0%} vs neighbor)"
                )
    return tuple(points), fragile, DataLimitations(CODES=frozenset({"rates_unverified"}))
