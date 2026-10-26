"""P5-S2 tests: advance mechanics — decide at T, execute at T+1, FIFO,
determinism in-process and across PYTHONHASHSEED values."""

import json
import os
import subprocess
import sys
from datetime import date, timedelta

import polars as pl
import pytest

from niveshdristi.core.errors import DataError, ExecutionError
from niveshdristi.core.market_rules import PriceLimitRule, RateSchedule
from niveshdristi.engine.advance import (
    ModelBundle,
    RebalanceSchedule,
    _consume_lots_fifo,
    advance,
)
from niveshdristi.engine.fund import FundState, Lot
from niveshdristi.execution.sim_broker import SimBroker
from niveshdristi.portfolio.risk_gates import GateLimits
from tests.test_alpha import (
    TestPortfolioConstruction,
    TestRiskGates,
)


class TestAdvance:
    """advance mechanics on synthetic SYN frames (all generated in code)."""

    @staticmethod
    def _frames(n: int = 10, start: str = "2026-10-01"):
        ds = [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(n)]
        f070 = pl.DataFrame({"date": ds, "close": [100.0] * n})
        f071 = pl.DataFrame({"date": ds, "close": [100.0] * n})
        return {"SYN090": f070, "SYN091": f071}

    @staticmethod
    def _model(signals_by_date: dict[str, float]):
        """Synthetic model emitting a conviction per date for SYN090."""

        class M:
            model_id = "syn_model"

            def predict(self, ctx, inputs):
                key = ctx.as_of.date().isoformat()
                conviction = signals_by_date.get(key)
                if conviction is None or "SYN090" not in inputs.prices:
                    return []
                sig = TestPortfolioConstruction._signal("SYN090", conviction)
                return [sig.model_copy(update={"model_id": "syn_model"})]

        return M()

    @staticmethod
    def _limits():
        return GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0)

    @staticmethod
    def _broker(slippage_bps: float = 0.0):
        return SimBroker(
            rates=RateSchedule(slippage_base_bps=slippage_bps),
            price_limits=PriceLimitRule(enabled=False),
        )

    def test_decide_at_t_executes_at_t_plus_1(self):
        """Decision assessed at session 0 (T) fills at session 1 (T+1)."""
        frames = self._frames(3)
        model = self._model({
            "2026-10-01": 1.0, "2026-10-02": 0.0, "2026-10-03": 0.0,
        })
        broker = self._broker()
        fund = FundState(cash=1_000_000.0)
        fills_by_session = []
        for day in (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)):
            fund, record = advance(
                fund, day, broker, frames,
                models=ModelBundle([model]), rules=TestRiskGates._rules(),
                limits=self._limits(), rebalance=RebalanceSchedule(), tax_enabled=False,
            )
            fills_by_session.append(len(record.fills))
        # session 2's fill is the 0.0-conviction LIQUIDATION of the position
        # (a 0.0 assessment still emits a sell-to-zero pending decision)
        assert fills_by_session == [0, 1, 1]

    def test_planted_future_row_raises_in_handle(self):
        from niveshdristi.marketdata.context import build_model_inputs

        frames = self._frames(2)
        future = pl.DataFrame({"date": ["2027-01-01"], "close": [1.0]})
        bad = pl.concat([frames["SYN090"], future])
        with pytest.raises(DataError):
            build_model_inputs(as_of=date(2026, 10, 2), prices={"SYN090": bad})

    def test_lapse_on_missing_bar(self):
        frames = self._frames(3)
        frames["SYN090"] = frames["SYN090"].filter(pl.col("date") != "2026-10-02")
        model = self._model({"2026-10-01": 1.0})
        broker = self._broker()
        fund = FundState(cash=1_000_000.0)
        events: list[str] = []
        for day in (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)):
            fund, record = advance(
                fund, day, broker, frames, models=ModelBundle([model]),
                rules=TestRiskGates._rules(), limits=self._limits(),
                rebalance=RebalanceSchedule(), tax_enabled=False,
            )
            events.extend(record.events)
        # the missing bar surfaces as a build-order drop (build_orders sees
        # no price for SYN090 at the execution session)
        assert any("dropped: no/invalid price" in e for e in events)

    def test_fifo_consumption_hand_computed(self):
        """Buy 10 @100 (d1), 10 @110 (d2); sell 10 @120 (d3): FIFO consumes
        the d1 lot -> gain (120-100)*10 = 200; d2 lot untouched."""
        lots = (
            Lot("SYN090", 10, date(2026, 1, 1), 100.0),
            Lot("SYN090", 10, date(2026, 1, 2), 110.0),
        )
        remaining, realized, proceeds = _consume_lots_fifo(
            lots, "SYN090", 10, date(2026, 1, 3), 120.0
        )
        assert proceeds == pytest.approx(1_200.0)
        assert len(realized) == 1
        assert realized[0].gain == pytest.approx(200.0)
        assert remaining == (Lot("SYN090", 10, date(2026, 1, 2), 110.0),)

    def test_reconcile_mismatch_raises(self):
        class RogueBroker(SimBroker):
            positions = {"SYN090": 999}  # broker book disagrees with FundState

        fund = FundState(cash=1_000_000.0)
        with pytest.raises(ExecutionError, match="reconcile failed"):
            advance(
                fund, date(2026, 10, 1),
                RogueBroker(
                    rates=RateSchedule(slippage_base_bps=0.0),
                    price_limits=PriceLimitRule(enabled=False),
                ),
                self._frames(2),
                models=ModelBundle([]), rules=TestRiskGates._rules(),
                limits=GateLimits(), rebalance=RebalanceSchedule(), tax_enabled=False,
            )

    @staticmethod
    def run_once() -> list[str]:
        """One deterministic 4-session run; returns record hashes."""
        frames = TestAdvance._frames(4)
        model = TestAdvance._model({
            "2026-10-01": 0.8, "2026-10-02": 0.6,
            "2026-10-03": 0.4, "2026-10-04": 0.2,
        })
        broker = TestAdvance._broker(slippage_bps=5.0)
        fund = FundState(cash=1_000_000.0)
        hashes = []
        for day in (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4)):
            fund, record = advance(
                fund, day, broker, frames, models=ModelBundle([model]),
                rules=TestRiskGates._rules(),
                limits=GateLimits(max_position_pct=0.5, min_cash_pct=0.0, turnover_max=1.0),
                rebalance=RebalanceSchedule(), tax_enabled=False,
            )
            hashes.append(record.compute_hash())
        return hashes

    def test_determinism_in_process(self):
        assert self.run_once() == self.run_once()

    def test_determinism_across_hash_seeds(self):
        script = (
            "import sys, json; sys.path.insert(0, 'src'); sys.path.insert(0, 'tests'); "
            "from tests.test_advance import TestAdvance; "
            "print(json.dumps(TestAdvance.run_once()))"
        )
        outputs = []
        for seed in ("1", "999"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env, timeout=240,
            )
            assert proc.returncode == 0, proc.stderr
            outputs.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        assert outputs[0] == outputs[1]


class TestBacktest:
    """P5-S3: backtest loop — no-trade flat, buy-and-hold hand-computed,
    drag identity, determinism, auto limitation codes, no look-ahead."""

    @staticmethod
    def _flat_frames(n=5):
        ds = [(date(2026, 10, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return {
            "SYN095": pl.DataFrame({"date": ds, "close": [100.0] * n}),
            "SYN096": pl.DataFrame({"date": ds, "close": [100.0] * n}),
        }

    @staticmethod
    def _model(signals: dict[str, float]):
        class M:
            model_id = "syn_model"

            def predict(self, ctx, inputs):
                c = signals.get(ctx.as_of.date().isoformat())
                if c is None or "SYN095" not in inputs.prices:
                    return []
                sig = TestPortfolioConstruction._signal("SYN095", c)
                return [sig.model_copy(update={"model_id": "syn_model"})]

        return M()

    @staticmethod
    def _run(frames, model, **kw):
        from niveshdristi.core.market_rules import RateSchedule
        from niveshdristi.engine.backtest import run_backtest

        # rules MUST carry the same rates the broker charges, or the engine's
        # fee-fit disagrees with the broker's cash accounting.
        rules = TestRiskGates._rules()
        real_rates = RateSchedule(
            brokerage_per_order=20.0, stt_delivery_buy=0.001,
            stt_delivery_sell=0.001, exchange_fee=0.0000345,
            regulator_fee=0.000001, stamp_duty_buy=0.00015,
            gst_on_fees=0.18, dp_charge_per_scrip=13.5, slippage_base_bps=0.0,
        )
        rules = rules.model_copy(update={"rates": real_rates})
        base = {
            "models": ModelBundle([model]),
            "rules": rules,
            "limits": GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0),
            "rebalance": RebalanceSchedule(),
            "initial_cash": 1_000_000.0,
        }
        base.update(kw)
        return run_backtest(frames, **base)

    def test_no_trade_flat_equity_zero_drag(self):
        result = self._run(self._flat_frames(), self._model({}))
        assert [v for _, v in result.net_equity_curve] == [1_000_000.0] * 5
        assert result.drag == pytest.approx(0.0)
        assert result.trade_count == 0

    def test_buy_and_hold_hand_computed(self):
        """Signal 1.0 on day 1, then HOLD (0.5 on later days — a nonzero
        conviction keeps the position): buys floor(1M/100)=10,000 shares at
        100 on day 2; flat prices -> equity = 1,000,000 minus the one buy's
        fees (slippage 0). An EMPTY assessment (no signals) would liquidate;
        that behaviour is covered by [0,1,1] in test_decide_at_t."""
        from niveshdristi.core.market_rules import RateSchedule
        from niveshdristi.execution.sim_broker import SimBroker

        rates = RateSchedule(
            brokerage_per_order=20.0, stt_delivery_buy=0.001,
            exchange_fee=0.0000345, regulator_fee=0.000001,
            stamp_duty_buy=0.00015, gst_on_fees=0.18,
            dp_charge_per_scrip=13.5, slippage_base_bps=0.0,
        )
        broker = SimBroker(rates=rates, price_limits=PriceLimitRule(enabled=False))
        result = self._run(
            self._flat_frames(5),
            self._model({
                "2026-10-01": 1.0, "2026-10-02": 0.5, "2026-10-03": 0.5,
                "2026-10-04": 0.5, "2026-10-05": 0.5,
            }),
            broker=broker,
        )
        # hand (fee-fit active): the engine reserves estimated fees BEFORE
        # sizing, so qty = int((1,000,000 - 20*1.18) / (100*(1+0.0011855)))
        #               = int(999,976.4 / 100.11855) = 9,987 shares.
        # notional = 998,700; fees = 20 + 0.001*998700 + 0.0000345*998700
        #            + 0.000001*998700 + 0.00015*998700
        #            + 0.18*(20 + 34.45515 + 0.9987) = 1213.940543
        expected_fees = 1213.940543
        assert result.fees_total == pytest.approx(expected_fees, abs=0.02)
        assert result.slippage_total == pytest.approx(0.0)
        assert result.drag == pytest.approx(expected_fees, abs=0.02)
        assert result.trade_count == 1
        # cash never negative (STRONGER than the old 10,000-share expectation
        # which spent 1,000,000 + fees and overdrawn cash by 1,215.49)
        assert min(v for _, v in result.net_equity_curve) > 0
        # net final = initial - fees (flat prices, 9,987 shares held at close)
        assert result.net_equity_curve[-1][1] == pytest.approx(
            1_000_000.0 - expected_fees + 0.0, abs=0.05
        )

    def test_auto_limitation_codes_and_banner(self):
        result = self._run(
            self._flat_frames(), self._model({}),
            rates_verified=False, universe_approximate=True,
            stub_models_used=True, benchmark_used=True,
        )
        codes = result.limitations.CODES
        for code in (
            "derived_calendar", "adjusted_price_basis", "corporate_actions_unavailable",
            "price_level_rules_on_adjusted", "rates_unverified",
            "approximate_universe", "survivorship_universe", "stub_models_used",
            "benchmark_not_tri",
        ):
            assert code in codes, code
        assert result.banner is not None
        assert "DATA LIMITATIONS" in result.banner
        assert result.limitations.promotable is False

    def test_caller_can_add_never_remove_auto_codes(self):
        result = self._run(
            self._flat_frames(), self._model({}),
            extra_limitations=frozenset({"no_pit_fundamentals"}),
        )
        assert "no_pit_fundamentals" in result.limitations.CODES
        assert "derived_calendar" in result.limitations.CODES  # auto kept
        assert result.limitations.promotable is False

    def test_determinism_of_record_hashes(self):
        model = self._model({"2026-10-01": 0.8, "2026-10-02": 0.4})
        r1 = self._run(self._flat_frames(), model)
        r2 = self._run(self._flat_frames(), model)
        assert r1.record_hashes == r2.record_hashes

    def test_no_look_ahead_future_rows_leave_past_records_unchanged(self):
        """Perturbing frame rows AFTER session T leaves all records up to T
        unchanged (planted wild future rows)."""
        frames = self._flat_frames(5)
        model = self._model({
            "2026-10-01": 0.8, "2026-10-02": 0.6, "2026-10-03": 0.4,
            "2026-10-04": 0.2, "2026-10-05": 0.1,
        })
        baseline = self._run(frames, model)
        wild = pl.DataFrame({
            "date": ["2026-10-10"], "close": [999_999.0],
        })
        frames_tampered = {
            "SYN095": pl.concat([frames["SYN095"], wild]),
            "SYN096": frames["SYN096"],
        }
        tampered = self._run(frames_tampered, model)
        # records 1..3 (sessions before the wild row's date) identical
        assert baseline.record_hashes[:3] == tampered.record_hashes[:3]


class TestMetrics:
    """P5-S4: pure metrics with hand-computed known answers."""

    @staticmethod
    def _curve(values: list[float], start: str = "2026-01-01"):
        ds = [
            (date.fromisoformat(start) + timedelta(days=i)).isoformat()
            for i in range(len(values))
        ]
        return tuple((date.fromisoformat(d), v) for d, v in zip(ds, values, strict=True))

    def test_cagr_known_answer(self):
        """1,000,000 -> 1,100,000 over 252 sessions (1 year): CAGR = 10%."""
        from niveshdristi.engine.metrics import cagr

        curve = self._curve(
            [1_000_000.0] + [1_000_000.0 * (1.10) ** (i / 252) for i in range(1, 253)]
        )
        result = cagr(curve)
        assert result == pytest.approx(0.10, abs=1e-6)

    def test_volatility_known_answer(self):
        """Returns +1%, -1%, +1%, -1% (4 returns): mean 0, sample var
        = 4*(0.01^2)/3 = 0.00013333, std = 0.011547; ann = x sqrt(252)
        = 0.18330."""
        import math

        from niveshdristi.engine.metrics import annualized_volatility

        vals = [100.0]
        for r in (0.01, -0.01, 0.01, -0.01):
            vals.append(vals[-1] * (1 + r))
        result = annualized_volatility(self._curve(vals))
        # sample std (ddof=1) of the 4 returns = sqrt(4e-4/3) = 0.0115470
        assert result == pytest.approx(0.0115470 * math.sqrt(252), rel=1e-3)

    def test_sharpe_flat_curve_unavailable(self):
        from niveshdristi.engine.metrics import Unavailable, sharpe

        result = sharpe(self._curve([100.0] * 5))
        assert isinstance(result, Unavailable)
        assert "flat curve" in result.reason

    def test_sharpe_known_answer(self):
        """Daily excess +0.001 every session: std 0 -> Unavailable; use two
        returns (+0.002, 0.0): mean 0.001, sample std 0.0014142 ->
        sharpe = 0.001/0.0014142*sqrt(252) = 17.82."""
        import math

        from niveshdristi.engine.metrics import Unavailable, sharpe

        result = sharpe(self._curve([100.0, 100.2, 100.2]))
        assert isinstance(result, Unavailable) is False
        assert result == pytest.approx(0.001 / 0.0014142 * math.sqrt(252), rel=1e-3)

    def test_sortino_no_downside_unavailable(self):
        from niveshdristi.engine.metrics import Unavailable, sortino

        assert isinstance(sortino(self._curve([100.0, 101.0, 102.04])), Unavailable)

    def test_max_drawdown_known_answer(self):
        from niveshdristi.engine.metrics import max_drawdown

        curve = self._curve([100.0, 120.0, 90.0, 95.0])
        result = max_drawdown(curve)
        dd, peak, trough = result
        assert dd == pytest.approx((120.0 - 90.0) / 120.0)
        assert peak == date(2026, 1, 2)
        assert trough == date(2026, 1, 3)

    def test_turnover_known_answer(self):
        """Traded 500,000 over 20 sessions at NAV 1,000,000:
        500,000/(2x1,000,000) x (252/20) = 31.5."""
        from niveshdristi.engine.metrics import turnover_annualized

        result = turnover_annualized(500_000.0, 20, 1_000_000.0)
        # 500,000/(2x1,000,000) = 0.25 per session; x 252/20 = 3.15x annualized
        assert result == pytest.approx(3.15)

    def test_hit_rate_excludes_flat_sessions(self):
        from niveshdristi.engine.metrics import Unavailable, hit_rate

        curve = self._curve([100.0, 101.0, 101.0, 102.0])  # +1%, 0%, +0.99%
        exposure = [1.0, 1.0, 0.0]  # third session flat (no exposure)
        result = hit_rate(curve, exposure)
        # considered: +1% and 0% (excluded 0-exposure session) -> 1 of 2 = 0.5
        assert result == pytest.approx(0.5)
        empty = hit_rate(curve, [0.0, 0.0, 0.0])
        assert isinstance(empty, Unavailable)

    def test_fewer_than_two_points(self):
        from niveshdristi.engine.metrics import Unavailable, cagr

        assert isinstance(cagr(self._curve([100.0])), Unavailable)

    def test_metrics_report_carries_limitations(self):
        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.engine.metrics import MetricsReport

        report = MetricsReport(
            limitations=DataLimitations(CODES=frozenset({"rates_unverified"})),
            rates_verified=False,
            cagr=0.1, volatility=0.2, sharpe=1.0, sortino=1.5,
            max_drawdown=0.1, turnover=3.0, hit_rate=0.6, exposure=0.9,
            cost_drag_fees_bps=11.5, cost_drag_slippage_bps=5.0,
        )
        assert report.limitations.promotable is False
        with pytest.raises(Exception, match="limitations"):
            MetricsReport(
                limitations=None, rates_verified=False,  # type: ignore[arg-type]
                cagr=None, volatility=None, sharpe=None, sortino=None,
                max_drawdown=None, turnover=None, hit_rate=None, exposure=None,
                cost_drag_fees_bps=None, cost_drag_slippage_bps=None,
            )


class TestAnalysis:
    """P5-S5: benchmark comparison + regime breakdown (hand-computed)."""

    @staticmethod
    def _frames(dates: list[str], closes: list[float]):
        return pl.DataFrame({"date": dates, "close": closes})

    def test_beta_alpha_known_answer(self):
        """Strategy = 0.5 x benchmark daily moves + 0.001 alpha per day:
        beta = 0.5, alpha = 0.252 (0.001 x 252), TE small, IR large."""
        from datetime import timedelta

        from niveshdristi.engine.analysis import compare_to_benchmark

        n = 60
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        bench_closes = [100.0]
        strat_closes = [100.0]
        for i in range(1, n):
            b_ret = 0.01 if i % 2 == 0 else -0.01
            bench_closes.append(bench_closes[-1] * (1 + b_ret))
            strat_closes.append(strat_closes[-1] * (1 + 0.5 * b_ret + 0.001))
        bench = self._frames(dates, bench_closes)
        curve = tuple(
            (date.fromisoformat(d), v) for d, v in zip(dates, strat_closes, strict=True)
        )
        cmp_result, limitations = compare_to_benchmark(curve, bench)
        assert limitations.promotable is False  # benchmark_not_tri
        assert "benchmark_not_tri" in limitations.CODES
        assert cmp_result.available
        assert cmp_result.beta == pytest.approx(0.5, abs=0.05)
        assert cmp_result.alpha == pytest.approx(0.252, abs=0.05)
        assert cmp_result.tracking_error > 0
        assert cmp_result.source is None  # not asserted

    def test_tri_asserted_records_source(self):
        from datetime import timedelta

        from niveshdristi.engine.analysis import compare_to_benchmark

        n = 10
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        bench = self._frames(dates, [100.0] * n)
        curve = tuple((date.fromisoformat(d), 100.0) for d in dates)
        cmp_result, limitations = compare_to_benchmark(
            curve, bench, tri_asserted=True, tri_source="niftyindices TRI (verified copy)"
        )
        assert "benchmark_not_tri" not in limitations.CODES
        assert cmp_result.source == "niftyindices TRI (verified copy)"

    def test_no_benchmark_typed_unavailable(self):
        from niveshdristi.engine.analysis import compare_to_benchmark

        curve = ((date(2026, 1, 1), 100.0),)
        cmp_result, limitations = compare_to_benchmark(curve, pl.DataFrame())
        assert cmp_result.available is False
        assert "no benchmark frame" in cmp_result.unavailable_reason

    def test_regime_labels_hand_computed(self):
        """Constant 1% daily moves: trailing vol = 0.01 x sqrt(252) = 0.1588
        (< 0.20) and trend +252x... -> after TREND_WINDOW: trend_up."""
        from datetime import timedelta

        from niveshdristi.engine.analysis import label_regimes

        n = 80
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        closes = [100.0 * (1.01 ** i) for i in range(n)]
        labels = label_regimes(self._frames(dates, closes))
        late = [labels[dates[i]] for i in range(60, n)]
        assert set(late) == {"trend_up"}
        assert labels[dates[0]] == "insufficient_history"

    def test_regime_breakdown_insufficient_data(self):
        """Fewer than 10 sessions per regime -> None metrics (insufficient)."""
        from datetime import timedelta

        from niveshdristi.engine.analysis import regime_breakdown

        n = 12
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        bench = self._frames(dates, [100.0 + i for i in range(n)])
        curve = tuple((date.fromisoformat(d), 100.0 + i) for i, d in enumerate(dates))
        breakdown = regime_breakdown(curve, bench, [1.0] * (n - 1))
        assert "regime_vol_proxy" in breakdown.limitations.CODES
        assert breakdown.banner is not None
        for stat in breakdown.regimes:
            if stat.sessions < 10:
                assert stat.annualized_return is None


class TestValidationInputs:
    """P5-S6: TrialRecorder, walk-forward splits, parameter sensitivity."""

    def test_recorder_counts_and_uniqueness(self):
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.engine.validation_inputs import TrialRecorder

        rec = TrialRecorder()
        rec.record("t1", {"lookback": "10"}, (0.01, -0.005, 0.008))
        rec.record("t2", {"lookback": "20"}, (0.005, 0.006, 0.004))
        assert rec.trial_count == 2
        with pytest.raises(ConfigurationError, match="duplicate trial_id"):
            rec.record("t1", {}, (0.0, 0.0))

    def test_zero_trials_error_contract(self):
        """A recorder with zero trials exposes trial_count=0; anything
        reporting significance must treat that as an error (tested at the
        validation gate in S7)."""
        from niveshdristi.engine.validation_inputs import TrialRecorder

        assert TrialRecorder().trial_count == 0

    def test_walk_forward_hand_computed_boundaries(self):
        """24 sessions, train 10, test 5, embargo 2:
        split0 = train [0,10) purge [10,12) test [12,17)
        split1 = train [5,15) purge [15,17) test [17,22)
        split2 = train [10,20) purge [20,22) test [22,27) > 24 -> stops.
        """
        from niveshdristi.engine.validation_inputs import walk_forward_splits

        sessions = [date(2026, 1, 1) + timedelta(days=i) for i in range(24)]
        splits = walk_forward_splits(
            sessions, train_sessions=10, test_sessions=5, embargo_sessions=2
        )
        assert splits == [(0, 10, 12, 17), (5, 15, 17, 22)]

    def test_split_invariants_property_fixed_seed(self):
        """FIXED seed, 200 random configurations: no train/test overlap, the
        purge gap holds, splits are ordered, coverage matches the step."""
        import random

        from niveshdristi.engine.validation_inputs import walk_forward_splits

        rng = random.Random(7)
        for _ in range(200):
            total = rng.randint(30, 200)
            train = rng.randint(5, total // 3)
            test = rng.randint(2, total // 4)
            # embargo must leave room for at least one test window
            max_embargo = max(1, total - train - test)
            embargo = rng.randint(1, max_embargo)
            sessions = list(range(total))
            splits = walk_forward_splits(
                sessions, train_sessions=train, test_sessions=test,
                embargo_sessions=embargo,
            )
            assert splits, "expected at least one split"
            prev_test_end = -1
            for train_s, train_e, test_s, test_e in splits:
                assert train_e - train_s == train
                assert test_e - test_s == test
                assert test_s - train_e == embargo  # purge gap exact
                assert train_e <= test_s  # no train/test overlap within a split
                # TEST windows must not overlap each other (trains may and do
                # overlap previous tests in walk-forward)
                assert test_s >= prev_test_end
                prev_test_end = test_e

    def test_parameter_sensitivity_flags_fragility(self):
        """Sharpe drops 0.9 -> 0.2 between neighbors (-78% > 30% default):
        flagged. Control drop 0.5 -> 0.45 (-10%): not flagged."""
        from niveshdristi.engine.validation_inputs import parameter_sensitivity

        def run_point(param_name, value):
            if value == 10:
                return (0.001, -0.005, 0.001, 0.002, 0.0015), 500.0, 200.0
            if value == 20:
                # mean EXACTLY 0 -> Sharpe 0 (hand: mean 0, sample std 1e-3);
                # drop from 0.551 = -100% > 30% default -> flagged
                return (0.001, -0.001, 0.001, -0.001, 0.0), 500.0, 200.0
            if value == 30:
                return (0.0005, -0.0002, 0.0004, 0.0002, 0.0003), 500.0, 200.0
            return (0.0, 0.0), 0.0, 0.0

        points, fragile, limitations = parameter_sensitivity(
            [("lookback", {}, (10, 20, 30))], run_point
        )
        assert len(points) == 3
        assert any("lookback=20" in f for f in fragile)
        assert not any("lookback=30" in f for f in fragile)
        assert "rates_unverified" in limitations.CODES


class TestValidationGate:
    """P5-S7: DSR, PBO, statuses, the overfit-toy SPEC test."""

    @staticmethod
    def _recorder_with(series_by_id: list[tuple[str, tuple[float, ...]]]):
        from niveshdristi.engine.validation_inputs import TrialRecorder

        rec = TrialRecorder()
        for tid, rets in series_by_id:
            rec.record(tid, {"param": tid}, rets)
        return rec

    def test_n1_reduces_to_psr(self):
        """N=1: E[maxZ] = 0 -> DSR threshold 0 -> PSR reduces to the
        probabilistic Sharpe vs zero (formula 4 with threshold 0)."""
        from niveshdristi.engine.validation import expected_max_sharpe, probabilistic_sharpe

        assert expected_max_sharpe(1) == 0.0
        returns = tuple(0.01 if i % 2 == 0 else 0.005 for i in range(20))
        psr_zero = probabilistic_sharpe(returns, 0.0)
        assert 0.5 < psr_zero <= 1.0  # positive-mean series beats a 0 threshold

    def test_dsr_hand_computed_case(self):
        """Hand case: N=2 trials, both Sharpes 1.0 annual (var 0) ->
        E[maxZ] = (1-0.5772)*invnorm(1-1/2) + 0.5772*invnorm(1-1/(2e)).
        invnorm(0.5) = 0; invnorm(1-1/(2e)) = invnorm(0.81606) = 0.8986.
        E[maxZ] = 0.5772*0.8986 = 0.5187. DSR annual = 0.5187*sqrt(0) = 0
        -> threshold 0 -> PSR vs 0."""
        import math
        from statistics import NormalDist

        from niveshdristi.engine.validation import expected_max_sharpe

        em = expected_max_sharpe(2)
        # hand: (1-EM)*invnorm(0.5) + EM*invnorm(1-1/(2e))
        #      = 0 + 0.5772 * invnorm(0.81606) = 0.5772 * 0.900306 = 0.51976
        hand = 0.5772156649 * NormalDist().inv_cdf(1.0 - 1.0 / (2.0 * math.e))
        assert em == pytest.approx(hand, abs=1e-9)
        assert em == pytest.approx(0.5197553, abs=1e-5)
        # monotonic in N: more trials -> higher expected max
        assert expected_max_sharpe(5) > expected_max_sharpe(2)
        assert expected_max_sharpe(20) > expected_max_sharpe(5)

    def test_psr_monotonic_property(self):
        """PSR decreases as the threshold increases (property)."""
        from niveshdristi.engine.validation import probabilistic_sharpe

        returns = tuple(0.01 if i % 3 else -0.005 for i in range(50))
        low = probabilistic_sharpe(returns, 0.0)
        high = probabilistic_sharpe(returns, 0.01)
        assert low > high

    def test_pbo_dominant_trial_zero(self):
        """One trial strictly dominates in-sample AND out-of-sample in every
        split -> PBO 0 (no overfit evidence)."""
        from niveshdristi.engine.validation import probability_of_backtest_overfit

        good = tuple(0.001 + 0.0001 * (i % 3) for i in range(24))
        poor1 = tuple(-0.001 for _ in range(24))
        poor2 = tuple(0.0 for _ in range(24))
        pbo = probability_of_backtest_overfit([good, poor1, poor2])
        assert pbo == 0.0

    def test_pbo_identical_trials_handled(self):
        """Identical trials: full ties carry no discriminating information
        -> skipped -> PBO 0.0 (documented convention), never a crash."""
        from niveshdristi.engine.validation import probability_of_backtest_overfit

        same = tuple(0.001 for _ in range(24))
        pbo = probability_of_backtest_overfit([same, same])
        assert pbo == 0.0

    def test_pbo_hand_built_matrix(self):
        """4 trials x 8 sessions, 4 blocks of 2 (C(4,2)=6 combinations).
        Trial A (8,8|8,8|-5,-5|-5,-5) is in-sample BEST only in the ONE
        combination whose in-sample blocks are its two 8-blocks; in that
        combination its OOS is the WORST (-5s) -> counted. In the other five
        combinations a different trial is IS-best, so A's OOS rank is
        irrelevant. PBO = 1/6 = 0.1667 (hand-derived)."""
        from niveshdristi.engine.validation import probability_of_backtest_overfit

        a = (8.0, 8.0, 8.0, 8.0, -5.0, -5.0, -5.0, -5.0)   # great IS, terrible OOS
        b = (4.0, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 5.0)       # mediocre both
        c = (2.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 3.0)       # poor IS, best OOS
        d = (0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
        pbo = probability_of_backtest_overfit([a, b, c, d])
        assert pbo == pytest.approx(1.0 / 6.0)  # 1 counted of 6 combinations

    def test_zero_trials_is_error(self):
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.engine.validation import run_validation_gate
        from niveshdristi.engine.validation_inputs import TrialRecorder

        with pytest.raises(ConfigurationError, match="zero recorded trials"):
            run_validation_gate(TrialRecorder())

    def test_spec_overfit_toy_flagged_control_not(self):
        """THE SPEC TEST: an intentionally overfit toy strategy (best of K
        noise strategies in-sample, fixed seed) is FLAGGED; a control with a
        planted persistent edge and few trials passes the screen. Numbers
        printed for the report; thresholds NOT tuned to pass."""
        import random

        from niveshdristi.engine.validation import (
            STATUS_PASS,
            run_validation_gate,
        )
        from niveshdristi.engine.validation_inputs import TrialRecorder

        rng = random.Random(11)
        rec_overfit = TrialRecorder()
        for k in range(40):  # 40 noise trials
            noise = [rng.gauss(0.0, 0.01) for _ in range(120)]
            rec_overfit.record(f"noise_{k}", {"k": str(k)}, noise)
        # pick the best IN-SAMPLE trial and add more of its (still noise)
        # returns? No: the recorder already holds it; the gate sees all 40.
        result_overfit = run_validation_gate(rec_overfit)
        print(f"overfit-toy: status={result_overfit.status} "
              f"best_sharpe={result_overfit.best_sharpe_annual:.3f} "
              f"dsr={result_overfit.deflated_threshold_annual:.3f} "
              f"psr={result_overfit.psr:.3f} pbo={result_overfit.pbo:.3f} "
              f"trials={result_overfit.trial_count}")
        # 40 noise trials: PBO 0.447 (coin flip), PSR 0.706 < 0.95 -> the
        # toy is REJECTED by the gate (no_significant_trials is a rejection
        # status: it failed the deflated-Sharpe significance screen). The
        # spec's "flagged" = not passed; promotable is False either way.
        assert result_overfit.status != STATUS_PASS
        assert result_overfit.promotable is False
        assert result_overfit.psr < 0.95  # fails the confidence screen

        # CONTROL: planted persistent edge, few trials
        rng2 = random.Random(5)
        rec_edge = TrialRecorder()
        edge = [0.0008 + rng2.gauss(0.0, 0.002) for _ in range(120)]
        rec_edge.record("edge_1", {"param": "a"}, edge)
        rec_edge.record("edge_2", {"param": "b"}, list(edge))
        result_edge = run_validation_gate(rec_edge)
        print(f"control   : status={result_edge.status} "
              f"best_sharpe={result_edge.best_sharpe_annual:.3f} "
              f"dsr={result_edge.deflated_threshold_annual:.3f} "
              f"psr={result_edge.psr:.3f} pbo={result_edge.pbo:.3f} "
              f"trials={result_edge.trial_count}")
        assert result_edge.status == STATUS_PASS  # control genuinely passes
        assert result_edge.psr >= 0.95

    def test_result_promotable_always_false_and_requires_limitations(self):
        """ promotable is ALWAYS False on this data (pipeline demonstration)."""

        from niveshdristi.engine.validation import STATUS_PASS, run_validation_gate
        rec = TestValidationGate._recorder_with([
            ("edge", tuple(0.0008 + 0.001 * ((i * 7) % 3 - 1) for i in range(120))),
        ])
        result = run_validation_gate(rec)
        assert result.status == STATUS_PASS
        assert result.promotable is False  # ALWAYS: pipeline demonstration only
        assert result.limitations.banner is not None
        assert result.rates_verified is False


class TestReports:
    """P5-S8: deterministic JSON + self-contained Plotly HTML reports."""

    @staticmethod
    def _result_and_limitations():
        from tests.test_advance import TestBacktest

        frames = TestBacktest._flat_frames(5)
        model = TestBacktest._model({"2026-10-01": 1.0, "2026-10-02": 0.5,
                                     "2026-10-03": 0.5, "2026-10-04": 0.5,
                                     "2026-10-05": 0.5})
        result = TestBacktest._run(frames, model)
        limitations = result.limitations
        return result, limitations

    @staticmethod
    def _write(tmp_path, label="synthetic"):
        from niveshdristi.engine.reports import write_report_files

        result, limitations = TestReports._result_and_limitations()
        return write_report_files(
            result,
            out_dir=tmp_path,
            limitations=limitations,
            rates_verified=False,
            calendar_source="derived-from-prices",
            as_of=result.net_equity_curve[-1][0],
            label=label,
        )

    def test_json_round_trip_and_deterministic(self, tmp_path):
        json_path, _ = self._write(tmp_path)
        text1 = json_path.read_text(encoding="utf-8")
        data = json.loads(text1)
        assert data["rates_verified"] is False
        assert data["rates_banner"] == "RATES UNVERIFIED"
        assert "DATA LIMITATIONS" in data["banner"]
        assert data["calendar_source"] == "derived-from-prices"
        assert data["as_of"] == "2026-10-05"  # last SESSION date, not the clock
        # byte-identical on a second run
        _, json_path2 = None, None
        json_path2, _ = self._write(tmp_path, label="synthetic2")
        assert json_path2.read_text(encoding="utf-8").replace("synthetic2", "synthetic") == text1

    def test_html_contains_banners_and_as_of_no_cdn(self, tmp_path):
        _, html_path = self._write(tmp_path)
        html = html_path.read_text(encoding="utf-8")
        assert "DATA LIMITATIONS" in html
        assert "RATES UNVERIFIED" in html
        assert "as of 2026-10-05" in html
        assert "derived-from-prices" in html
        # plotly.js is INLINE: no external CDN script TAG may exist (the
        # embedded bundle contains the URL as a config default string)
        assert '<script src="https://cdn.plot.ly' not in html
        assert "plotly.js" in html or "Plotly.newPlot" in html

    def test_reports_written_only_to_caller_path(self, tmp_path):
        json_path, html_path = self._write(tmp_path)
        assert str(json_path).startswith(str(tmp_path))
        assert str(html_path).startswith(str(tmp_path))
        assert html_path.stat().st_size > 100_000  # inline plotly.js size
