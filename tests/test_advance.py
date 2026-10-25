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
