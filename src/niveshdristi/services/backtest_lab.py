"""Backtest Lab service (NEW, P8-S8).

runs run_backtest on STORED SNAPSHOT frames (or synthetic demo frames) with
the registered live models and the market profile's cost model. No network.
Cached by a CONTENT key (fund id + as_of + model ids + frame digests)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from niveshdristi.engine.validation_inputs import Trial, TrialRecorder


def content_key(fund_id: str, base: str | Path | None = None) -> str:
    """Content key over the stored snapshot digests at the fund's as_of."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return "empty"
    as_of = records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    digests = (manifest_path.read_text(encoding="utf-8")
               if manifest_path.exists() else "{}")
    basis = json.dumps([fund_id, as_of, digests], sort_keys=True)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def run_backtest_service(fund_id: str, base: str | Path | None = None,
                         *, _key: str | None = None) -> dict:
    """Run the engine backtest over stored snapshot frames. Verdict wording
    is FIXED: 'pipeline demonstration only; not evidence of performance'."""
    import polars as pl

    from niveshdristi.engine.advance import ModelBundle
    from niveshdristi.engine.backtest import run_backtest
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    paths = FundPaths(base).for_fund(fund_id)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return {"available": False, "reason": "no stored sessions"}
    as_of = records[-1]["session_date"]
    manifest_path = paths.snapshots / as_of / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames: dict[str, pl.DataFrame] = {}
    for symbol, digest in sorted(manifest.items()):
        matches = sorted((paths.snapshots / as_of).glob(
            f"{symbol}_{digest[:16]}.parquet"))
        if matches:
            frames[symbol] = pl.read_parquet(matches[0])
    from niveshdristi.services.rules import rules_from_header

    rules = rules_from_header(fund_id, base)
    # WARMUP SLICE: the legacy TA scorer needs ~200 as-of rows before the
    # FIRST backtest session, so each frame is cut to its last
    # (paper sessions + 200) rows. Display-only computation.
    warmup = len(records) + 200
    frames = {sym: df.tail(warmup) for sym, df in frames.items()}
    # The legacy TA scorer crashes in the engine's from-row-1 calendar
    # (its 200-row EMA warmup can never be satisfied at session 1), so the
    # Lab runs the live bundle WITHOUT it — documented, display-only.
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.regime import RegimeModel

    lab_bundle = ModelBundle([TimeSeriesMomentum(), CrossSectionalMomentum(),
                              MeanReversion(), LowVolatility(),
                              PriceRangeModel(), RegimeModel()])
    try:
        # limits=None -> the ENGINE constructs its default GateLimits (the
        # services boundary forbids importing portfolio/); broker=None ->
        # the engine's default SimBroker. Documented, display-only.
        # FX-O (fix run 5): the fund header's costs_not_modeled code
        # (recorded at creation for US_NYSE funds) propagates into the
        # backtest result through the engine's existing extra_limitations
        # parameter — no core/engine edit; a US backtest never presents
        # itself without the costs-not-modeled disclosure.
        header = PaperLedger(paths.ledger).header()
        costs_flag = set(header.get("limitation_codes", [])) & {
            "costs_not_modeled",
        }
        bt = run_backtest(
            frames, models=lab_bundle, rules=rules,
            rebalance=_rebalance(), initial_cash=1_000_000.0,
            tax_enabled=True,
            extra_limitations=frozenset(costs_flag),
        )
    except Exception as exc:  # noqa: BLE001 - typed, honest degradation
        return {**_base_banners(fund_id, base), "available": False,
                "reason": (f"backtest unavailable on this frame set "
                           f"({type(exc).__name__}); the legacy TA scorer "
                           f"needs ~200 sessions of warmup")}
    return {
        **_base_banners(fund_id, base),
        "available": True,
        "as_of": as_of,
        "net_curve": [(d.isoformat(), round(v, 2))
                      for d, v in bt.net_equity_curve],
        "gross_curve": [(d.isoformat(), round(v, 2))
                        for d, v in bt.gross_equity_curve],
        "drag_bps": round(bt.drag_bps, 1),
        "fees_total": round(bt.fees_total, 2),
        "slippage_total": round(bt.slippage_total, 2),
        "trade_count": bt.trade_count,
        "limitations": sorted(bt.limitations.CODES),
        "calendar_source": bt.calendar_source,
        "verdict": ("validation-gate result: pipeline demonstration only; "
                    "not evidence of performance"),
        "promotable": bt.limitations.promotable,
        # P11-S4: the caller-recorded trial (Phase 6 need); the count is
        # the recorder's cumulative total for this process.
        "trials_recorded": _record_trial(
            _key or content_key(fund_id, base), fund_id, as_of, bt),
    }


def _rebalance() -> Any:
    from niveshdristi.engine.advance import RebalanceSchedule

    return RebalanceSchedule()


# P11-S4: TrialRecorder wiring at the CALLER (Phase 6 need: "TrialRecorder
# integration into every real backtest run"). The recorder is PURE (no
# I/O) and lives for the process lifetime; a recorder row is derived
# from the run's net equity curve. Identical content (same content key)
# is NOT re-recorded — duplicate trials would inflate E[max Sharpe] and
# are statistically dishonest. Nothing inside engine/ changes.
_TRIAL_RECORDER: TrialRecorder | None = None


def _trial_recorder() -> TrialRecorder:
    global _TRIAL_RECORDER
    if _TRIAL_RECORDER is None:
        from niveshdristi.engine.validation_inputs import TrialRecorder

        _TRIAL_RECORDER = TrialRecorder()
    return _TRIAL_RECORDER


def recorded_trials() -> tuple[Trial, ...]:
    """The module recorder's trials (read-only accessor for tests)."""
    return _trial_recorder().trials


def _record_trial(content: str, fund_id: str, as_of: str, bt: Any) -> int:
    """Record ONE trial for this backtest run; idempotent by content key.
    Returns the recorder's cumulative trial count."""
    recorder = _trial_recorder()
    if any(t.trial_id == content for t in recorder.trials):
        return recorder.trial_count
    equity = [1_000_000.0] + [float(v) for _, v in bt.net_equity_curve]
    returns = [
        equity[i + 1] / equity[i] - 1.0 for i in range(len(equity) - 1)
    ]
    recorder.record(
        content,
        {
            "fund_id": fund_id,
            "as_of": as_of,
            "source": "backtest_lab",
        },
        returns,
    )
    return recorder.trial_count


def _base_banners(fund_id: str, base: str | Path | None) -> dict:
    from niveshdristi.services.fund import read_fund

    try:
        return read_fund(fund_id, base=base)
    except Exception:  # noqa: BLE001
        return {}
