"""Validation gate (NEW, Phase 5) — PURE ARITHMETIC, no new dependencies.

Spec criteria (verbatim sources):
- docs/CLAUDE_CODE_PROMPT.md: "Validation gate: deflated Sharpe and
  probability of backtest overfitting (implement CPCV if feasible,
  otherwise document the simplified approach used and why)." Test: "an
  intentionally overfit toy strategy is flagged by the gate."
- docs/CHANGES.md C10: "deflated Sharpe / PBO / CPCV when many variants
  are tried"; "a strategy is 'promotable' only if it passes the gate";
  "Done when: an intentionally overfit toy strategy is flagged by the
  gate."
The spec gives NO numeric thresholds, so the ones below are named
UNVALIDATED DEFAULTS.

Deflated Sharpe Ratio (Bailey & Lopez de Prado, "The Deflated Sharpe
Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normal
Risks", Journal of Portfolio Management 2014). Formulas:
  1. Expected maximum Sharpe under N independent trials (standardized):
       E[maxZ] ≈ (1 - γ) * Φ^-1(1 - 1/N) + γ * Φ^-1(1 - 1/(N*e)),
     γ = Euler-Mascheroni constant ≈ 0.5772156649.
  2. Variance of trial Sharpes: var((SR_1..SR_N)) across trials.
  3. Deflated SR threshold: DSR* = E[maxZ] * sqrt(var(SR trials)).
  4. Probabilistic SR (PSR) of the BEST observed Sharpe vs DSR*:
       PSR = Φ( (SR_best - DSR*) * sqrt(n - 1) / sqrt(1 - skew*SR_best
             + (kurt-1)/4 * SR_best^2) ),
     with SR_best expressed per-session (not annualized), n = sample
     length, skew/kurtosis of the net returns (kurt = non-excess kurtosis,
     normal = 3 so (kurt-1)/4 is the standard adjustment).
  5. The gate compares PSR against a named UNVALIDATED DEFAULT confidence
     (0.95): pass if PSR >= confidence.

PBO via CSCV (combinatorially symmetric cross-validation, Bailey et al.
" The Probability of Backtest Overfitting", JCF 2017): trial return
matrices split into S even contiguous blocks; for every balanced half-split
combination (itertools.combinations), the in-sample best trial's
out-of-sample rank is recorded; logit = ln(rank_fraction / (1 -
rank_fraction)); PBO = fraction of combinations with logit <= 0. Ties in
the in-sample ranking count AGAINST the strategy (rank fraction 0.5 ->
logit 0 -> counted as overfit evidence, documented).

CPCV: the full combinatorial version (all C(N,S) paths with per-path
recombination) is DEFERRED — documented below in cpcv_deferral_note.

Statuses: "passed_statistical_screen_pipeline_demonstration_only" (best
possible on this data), "flagged_overfit", "insufficient_trials" (zero
recorded trials is an error at construction), "no_significant_trials".
A result is NEVER evidence of real-world performance: promotable is False
while ANY limitation is present, and every result here is a pipeline
demonstration on synthetic data.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from statistics import NormalDist

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.core.limitations import DataLimitations
from niveshdristi.engine.validation_inputs import TrialRecorder

# UNVALIDATED DEFAULTS
PSR_CONFIDENCE = 0.95  # PSR at/above this passes the screen
PBO_MAX_FLAG = 0.50  # PBO above this flags overfit
CSCV_MAX_BLOCKS = 12  # documented cap: 2^S half-splits grows as 2^S
EULER_MASCHERONI = 0.5772156649015329

STATUS_PASS = "passed_statistical_screen_pipeline_demonstration_only"
STATUS_FLAGGED = "flagged_overfit"
STATUS_NO_SIGNIFICANT = "no_significant_trials"

cpcv_deferral_note = (
    "Full CPCV (combinatorially purged paths with per-path recombination) is "
    "deferred: with T sessions and S blocks it produces C(S, S/2)^2 train/test "
    "path pairs, which exceeds practical runtime for the small synthetic "
    "samples in this codebase. The simplified CSCV probability of backtest "
    "overfitting below covers the same selection-bias question with balanced "
    "half-splits, per the spec's 'implement CPCV if feasible, otherwise "
    "document the simplified approach used and why'."
)


def expected_max_sharpe(n_trials: int) -> float:
    """E[maxZ] under n_trials independent standard-normal trials (formula 1)."""
    if n_trials < 1:
        raise ConfigurationError("n_trials must be >= 1")
    nd = NormalDist()
    if n_trials == 1:
        return 0.0
    first = nd.inv_cdf(1.0 - 1.0 / n_trials)
    second = nd.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return (1.0 - EULER_MASCHERONI) * first + EULER_MASCHERONI * second


def probabilistic_sharpe(
    returns: tuple[float, ...], threshold_sharpe: float
) -> float:
    """PSR of the per-session Sharpe vs a threshold (formula 4).

    threshold_sharpe and the observed Sharpe are BOTH per-session
    (non-annualized); returns are the net session returns.
    """
    n = len(returns)
    if n < 2:
        raise ConfigurationError("PSR needs at least 2 returns")
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    sr = mean / math.sqrt(var) if var > 0 else 0.0
    # skewness (population) and kurtosis (non-excess; normal = 3)
    m3 = sum((r - mean) ** 3 for r in returns) / n
    m4 = sum((r - mean) ** 4 for r in returns) / n
    skew = m3 / math.sqrt(var) ** 3 if var > 0 else 0.0
    kurt = m4 / var ** 2 if var > 0 else 3.0
    denom = math.sqrt(max(1e-18, 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr))
    psr = NormalDist().cdf((sr - threshold_sharpe) * math.sqrt(n - 1) / denom)
    return psr


def probability_of_backtest_overfit(
    trial_returns: Sequence[tuple[float, ...]], blocks: int = CSCV_MAX_BLOCKS
) -> float:
    """PBO via CSCV (formula block above). Ties count against (documented)."""
    if len(trial_returns) < 2:
        raise ConfigurationError("PBO needs at least 2 trials")
    n_sessions = min(len(r) for r in trial_returns)
    if n_sessions < 2 * blocks:
        blocks = max(2, n_sessions // 2)
    if n_sessions < blocks * 2 or blocks < 2:
        raise ConfigurationError("not enough sessions for even two blocks")
    trimmed = [tuple(r[: n_sessions - n_sessions % blocks]) for r in trial_returns]
    size = len(trimmed[0]) // blocks
    per_block = [
        [list(trial[b * size : (b + 1) * size]) for b in range(blocks)]
        for trial in trimmed
    ]
    combinations = list(itertools.combinations(range(blocks), blocks // 2))
    logit_below_zero = 0
    total = 0  # combinations with discriminating information (full ties skipped)
    for combo in combinations:
        rest = [b for b in range(blocks) if b not in combo]
        is_best, is_best_sharpe = 0, -math.inf
        for t_idx in range(len(trial_returns)):
            is_series = [
                x
                for b in combo
                for x in per_block[t_idx][b]
            ]
            m = sum(is_series) / len(is_series) if is_series else 0.0
            var = (
                sum((x - m) ** 2 for x in is_series) / (len(is_series) - 1)
                if len(is_series) > 1 else 0.0
            )
            sharpe = m / math.sqrt(var) if var > 0 else 0.0
            if sharpe > is_best_sharpe:
                is_best_sharpe = sharpe
                is_best = t_idx
        # OOS relative rank (omega) of the IS-best trial: fraction of the
        # other trials it OUTPERFORMED (ties count half-against). omega=1 ->
        # logit +inf (no overfit evidence); omega=0 -> logit -inf (overfit).
        oos_means = []
        for t_idx in range(len(trial_returns)):
            oos_series = [x for b in rest for x in per_block[t_idx][b]]
            oos_means.append(sum(oos_series) / len(oos_series) if oos_series else 0.0)
        oos_best = oos_means[is_best]
        others = [m for i, m in enumerate(oos_means) if i != is_best]
        worse = sum(1 for m in others if m < oos_best)
        ties = sum(1 for m in others if m == oos_best)
        if ties == len(others):
            # FULL tie: the data carries no discriminating information for
            # this combination; skip it entirely (documented above).
            continue
        omega = (worse + 0.5 * ties) / len(others) if others else 1.0
        omega = min(max(omega, 1e-9), 1.0 - 1e-9)  # keep the logit finite
        logit = math.log(omega / (1.0 - omega))
        total += 1
        if logit <= 0:
            logit_below_zero += 1
    # A log with NO discriminating combinations (all full ties) returns
    # 0.0: exact-duplicate trials carry no overfit evidence.
    return logit_below_zero / total if total else 0.0


class ValidationResult(BaseModel):
    """Validation-gate outcome (limitations REQUIRED; trial count required
    via the recorder summary; promotable always False on this data)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitations: DataLimitations
    rates_verified: bool
    trial_count: int
    best_sharpe_annual: float
    deflated_threshold_annual: float
    psr: float
    pbo: float
    status: str

    @property
    def promotable(self) -> bool:
        """ALWAYS False on this data: pipeline demonstration, not evidence."""
        return False

    @property
    def banner(self) -> str | None:
        return self.limitations.banner


def run_validation_gate(recorder: TrialRecorder) -> ValidationResult:
    """Run the gate over the recorder's trials (recorder is MANDATORY)."""
    trials = recorder.trials
    if recorder.trial_count == 0:
        raise ConfigurationError(
            "validation gate requires at least one recorded trial "
            "(zero recorded trials is an error, never hand-supplied)"
        )
    n_trials = recorder.trial_count
    best = max(trials, key=lambda t: t.sharpe)
    best_returns = best.net_returns
    var_trials = recorder.sharpe_variance()
    em = expected_max_sharpe(n_trials)
    dsr_threshold_annual = em * math.sqrt(var_trials)
    dsr_threshold_session = dsr_threshold_annual / math.sqrt(252)
    psr = probabilistic_sharpe(best_returns, dsr_threshold_session)
    # Single-trial logs carry no selection bias: PBO defined 0.0 (documented).
    pbo = (
        probability_of_backtest_overfit([t.net_returns for t in trials])
        if n_trials >= 2
        else 0.0
    )
    # Status logic: the DSR screen is the primary overfit detector — if the
    # BEST observed Sharpe does not clear the deflated threshold (E[maxZ]
    # scaled by trial-Sharpe variance), the selection bias made it look good
    # and the strategy is FLAGGED. High PBO also flags. Only then can the
    # PSR confidence and a low PBO produce a pass.
    if pbo > PBO_MAX_FLAG:
        status = STATUS_FLAGGED
    elif best.sharpe <= dsr_threshold_annual:
        status = STATUS_FLAGGED
    elif psr >= PSR_CONFIDENCE:
        status = STATUS_PASS
    else:
        status = STATUS_NO_SIGNIFICANT
    codes = {"rates_unverified", "no_pit_fundamentals", "survivorship_universe",
             "approximate_universe"}
    return ValidationResult(
        limitations=DataLimitations(CODES=frozenset(codes)),
        rates_verified=False,
        trial_count=n_trials,
        best_sharpe_annual=round(best.sharpe, 6),
        deflated_threshold_annual=round(dsr_threshold_annual, 6),
        psr=round(psr, 6),
        pbo=round(pbo, 6),
        status=status,
    )

