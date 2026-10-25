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
