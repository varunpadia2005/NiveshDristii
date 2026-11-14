"""P9-S3: the TWO-MARKET success criterion — the SAME run_backtest and one
paper-fund tick path run end to end for IN_NSE and US_NYSE on synthetic
data, with ZERO edits to core/ and engine/ (proven by the empty diff
pasted in the run evidence)."""

from __future__ import annotations

import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

from niveshdristi.markets.in_us.profile import COSTS_NOT_MODELED_CODE

REPO = Path(__file__).resolve().parent.parent


def _no_ta_bundle():
    """The Lab bundle (P8-S8): the live models MINUS the legacy TA scorer,
    whose 200-row warmup cannot be satisfied at the engine's session 1."""
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.regime import RegimeModel
    from niveshdristi.engine.advance import ModelBundle

    return ModelBundle([TimeSeriesMomentum(), CrossSectionalMomentum(),
                        MeanReversion(), LowVolatility(), PriceRangeModel(),
                        RegimeModel()])


def _frames(n=132):
    import polars as pl

    end = date(2026, 10, 30)
    dates = [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]
    c = [100.0 * (1.0025 ** i) for i in range(n)]
    common = {"date": dates, "close": c, "high": [v * 1.01 for v in c],
              "low": [v * 0.99 for v in c], "adj_close": c,
              "adj_high": [v * 1.01 for v in c], "adj_low": [v * 0.99 for v in c],
              "volume": [1_000_000] * n}
    return {"SYNA": pl.DataFrame(common), "SYNB": pl.DataFrame(common)}


class TestTwoMarketEngine:
    def test_backtest_runs_for_both_markets(self):
        from niveshdristi.engine.backtest import run_backtest
        from niveshdristi.markets import IN_NSE_PROFILE
        from niveshdristi.markets.in_us.profile import (
            COSTS_NOT_MODELED_CODE,
            us_market_rules,
        )
        frames = _frames(240)
        bundle = _no_ta_bundle()
        # INDIA: profile rules
        from niveshdristi.markets.registry import to_rules

        in_bt = run_backtest(frames, models=bundle,
                             rules=to_rules(IN_NSE_PROFILE),
                             limits=None, rebalance=_rb(),
                             initial_cash=1_000_000.0, tax_enabled=True,
                             rates_verified=False)
        assert "derived_calendar" in in_bt.limitations.CODES
        assert "rates_unverified" in in_bt.limitations.CODES
        assert "costs_not_modeled" not in in_bt.limitations.CODES

        # US: null-rate rules with the explicit flag
        us_rules, marker = us_market_rules(costs_not_modeled=True)
        us_bt = run_backtest(frames, models=bundle, rules=us_rules,
                             limits=None, rebalance=_rb(),
                             initial_cash=1_000_000.0, tax_enabled=False,
                             rates_verified=False,
                             extra_limitations=frozenset({COSTS_NOT_MODELED_CODE}))
        # P10-S2: costs_not_modeled is a first-class code; the banner/marker
        # carries the operator-facing text.
        assert "costs_not_modeled" in us_bt.limitations.CODES
        assert "derived_calendar" in us_bt.limitations.CODES
        assert marker["banner"] == "COSTS NOT MODELED"
        assert us_bt.trade_count == in_bt.trade_count  # same engine, same data

    def test_paper_tick_path_for_both_markets(self, tmp_path):
        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.markets import IN_NSE_PROFILE
        from niveshdristi.markets.in_us.profile import us_market_rules
        from niveshdristi.paper.fund import create_fund, tick

        frames = _frames(132)
        bundle = _no_ta_bundle()

        # US fund: costs_not_modeled in the header limitations
        us_rules, marker = us_market_rules(costs_not_modeled=True)
        create_fund("us_demo", base=tmp_path, created=date(2026, 6, 20),
                    config_digest="p9", rules=us_rules,
                    limitations=DataLimitations(CODES=frozenset({
                        "rates_unverified", "derived_calendar",
                        COSTS_NOT_MODELED_CODE})),
                    rates_verified=False, initial_cash=1_000_000.0,
                    universe=["SYNA", "SYNB"])
        result = tick("us_demo", base=tmp_path,
                      fetch_bars=lambda u, d: frames,
                      clock_now=date(2026, 10, 30), models=bundle,
                      rules=us_rules,
                      limits=None or _limits(), rebalance=None or _rb(),
                      universe=["SYNA", "SYNB"])
        assert result["outcome"] == "filled"
        header = json.loads(
            (tmp_path / "us_demo" / "ledger.jsonl").read_text(
                encoding="utf-8").splitlines()[0])
        us_digest = json.loads(header["market_rules_digest"])
        assert us_digest["market_id"] == "US_NYSE"
        # P10-S2: the header now carries the first-class code
        assert "costs_not_modeled" in header["limitation_codes"]



        # INDIA fund unchanged behaviour
        from niveshdristi.markets.registry import to_rules

        in_rules = to_rules(IN_NSE_PROFILE)
        create_fund("in_demo", base=tmp_path, created=date(2026, 6, 20),
                    config_digest="p9", rules=in_rules,
                    limitations=DataLimitations(
                        CODES=frozenset({"rates_unverified"})),
                    rates_verified=False, initial_cash=1_000_000.0,
                    universe=["SYNA", "SYNB"])
        r_in = tick("in_demo", base=tmp_path,
                    fetch_bars=lambda u, d: frames,
                    clock_now=date(2026, 10, 30), models=bundle,
                    rules=in_rules, limits=_limits(), rebalance=_rb(),
                    universe=["SYNA", "SYNB"])
        assert r_in["outcome"] == "filled"
        header_in = json.loads(
            (tmp_path / "in_demo" / "ledger.jsonl").read_text(
                encoding="utf-8").splitlines()[0])
        assert json.loads(header_in["market_rules_digest"])[
            "market_id"] == "IN_NSE"

    def test_currency_and_grouping_labels_differ(self):
        from niveshdristi.markets import IN_NSE_PROFILE
        from niveshdristi.markets.registry import get_registry
        from niveshdristi.services.format import format_compact, format_money

        us = get_registry().get("US_NYSE")
        assert format_money(1234567.89, IN_NSE_PROFILE) == "12,34,567.89"
        assert format_money(1234567.89, us) == "1,234,567.89"
        assert format_compact(25000000, IN_NSE_PROFILE) == "2.50 crore"
        assert format_compact(25000000, us) == "25.00 million"
        assert IN_NSE_PROFILE.currency == "INR"
        assert us.currency == "USD"

    def test_core_and_engine_unchanged(self):
        """Zero UNAPPROVED edits to core/ and engine/: the diff is taken
        against 04c1501 — the P10-S2 commit carrying the ONE approved core
        edit (costs_not_modeled, D4). Anything else appearing here is an
        unapproved core/engine change."""
        proc = subprocess.run(
            ["git", "diff", "--stat", "04c1501", "--", "src/niveshdristi/core",
             "src/niveshdristi/engine"],
            capture_output=True, text=True, cwd=REPO, timeout=60)
        assert proc.returncode == 0
        assert proc.stdout.strip() == "", proc.stdout


def _rb():
    from niveshdristi.engine.advance import RebalanceSchedule

    return RebalanceSchedule()


def _limits():
    from niveshdristi.portfolio.risk_gates import GateLimits

    return GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0)


class TestCostsNotModeledCode:
    """P10-S2 (D4): costs_not_modeled is now a FIRST-CLASS limitation code
    (core/limitations.py) — the Phase 9 deferral is resolved."""

    def test_costs_not_modeled_code_accepted(self):
        from niveshdristi.core.limitations import DataLimitations

        lim = DataLimitations(CODES=frozenset({"costs_not_modeled"}))
        assert "costs_not_modeled" in lim.CODES

    def test_us_backtest_carries_the_code(self, tmp_path):
        from niveshdristi.engine.backtest import run_backtest
        from niveshdristi.markets.in_us.profile import (
            COSTS_NOT_MODELED_CODE,
            us_market_rules,
        )
        from tests.test_paper import _momentum_frames
        from tests.test_two_market import _no_ta_bundle

        rules, marker = us_market_rules(costs_not_modeled=True)
        bt = run_backtest(_momentum_frames(240), models=_no_ta_bundle(),
                          rules=rules, limits=None, rebalance=_rb(),
                          initial_cash=1_000_000.0, tax_enabled=False,
                          rates_verified=False,
                          extra_limitations=frozenset({COSTS_NOT_MODELED_CODE}))
        assert COSTS_NOT_MODELED_CODE in bt.limitations.CODES
        assert marker["banner"] == "COSTS NOT MODELED"
