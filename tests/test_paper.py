"""P6-S2 tests: paper fund lifecycle, commit protocol, lock, tick semantics.

All frames are synthetic (SYN names, generated in code). Tests always pass
tmp_path as the fund base (amendment D) — the default location is never
written. No clock reads: the candidate date is an explicit argument.
"""

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from niveshdristi.core.errors import LedgerError, LockHeldError
from niveshdristi.core.limitations import DataLimitations
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.engine.advance import ModelBundle, RebalanceSchedule
from niveshdristi.paper.fund import Lock, create_fund, default_fund_root, tick
from niveshdristi.portfolio.risk_gates import GateLimits
from tests.test_advance import TestAdvance, TestRiskGates


class TestPaperFund:
    """P6-S2: fund lifecycle, commit protocol, lock, tick semantics."""

    @staticmethod
    def _frames(dates, closes_070=None, closes_071=None):
        f070 = pl.DataFrame({
            "date": dates,
            "close": closes_070 or [100.0] * len(dates),
            "volume": [1_000_000] * len(dates),
        })
        f071 = pl.DataFrame({
            "date": dates,
            "close": closes_071 or [100.0] * len(dates),
            "volume": [1_000_000] * len(dates),
        })
        return {"SYN090": f070, "SYN091": f071}

    @staticmethod
    def _model(signals: dict[str, float]):
        inner = TestAdvance._model(signals)
        return inner

    @staticmethod
    def _limits():
        return GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0)

    @staticmethod
    def _create(tmp_path, fund_id="paper_test", created=date(2026, 10, 1)):
        return create_fund(
            fund_id, base=tmp_path, created=created,
            config_digest="cfg", rules=MarketRules(market_id="TEST_M"),
            limitations=DataLimitations(CODES=frozenset({"rates_unverified"})),
            rates_verified=False, initial_cash=1_000_000.0,
            universe=["SYN090", "SYN091"],
        )

    def test_create_and_load(self, tmp_path):
        from niveshdristi.paper.fund import load_fund

        ledger_path = self._create(tmp_path)
        assert ledger_path.exists()
        ledger = load_fund("paper_test", base=tmp_path)
        assert ledger.header()["fund_id"] == "paper_test"
        assert ledger.last_session_date() is None  # header only

    def test_create_duplicate_fails(self, tmp_path):
        self._create(tmp_path)
        with pytest.raises(LedgerError, match="already exists"):
            self._create(tmp_path)

    def test_default_state_location_outside_repo(self):
        """Amendment D: the default root is under the user profile, outside
        the repo; tests never write there (they always pass a base)."""
        repo = Path(__file__).resolve().parent.parent
        root = default_fund_root()
        assert repo not in root.parents
        assert root != repo
        assert root == Path.home() / "niveshdristi" / "funds"

    def test_lock_exclusive_and_release(self, tmp_path):
        lock = Lock(tmp_path / "tick.lock")
        with lock:
            assert (tmp_path / "tick.lock").exists()
            with pytest.raises(LockHeldError, match="lock already held"):
                with Lock(tmp_path / "tick.lock"):
                    pass
        assert not (tmp_path / "tick.lock").exists()  # released

    def test_tick_idempotent_noop_byte_for_byte(self, tmp_path):
        """SPEC TEST (P6): ticking twice for the same session changes
        nothing — the second tick is a logged no-op and the ledger bytes are
        identical before/after."""
        ledger_path = self._create(tmp_path)
        frames = self._frames(["2026-10-01", "2026-10-02"])
        signals = {"2026-10-01": 0.8, "2026-10-02": 0.5}
        r1 = self._tick(tmp_path, frames, date(2026, 10, 2), signals)
        assert r1["outcome"] == "filled"
        before = ledger_path.read_bytes()
        r2 = self._tick(tmp_path, frames, date(2026, 10, 2), signals)
        assert r2["outcome"] == "no-op"
        assert "idempotent" in r2["reason"]
        assert ledger_path.read_bytes() == before  # byte-for-byte unchanged

    def test_catch_up_three_missed_sessions(self, tmp_path):
        ledger_path = self._create(tmp_path)
        dates = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
        frames = self._frames(dates)
        signals = dict.fromkeys(dates, 0.5)
        result = self._tick(tmp_path, frames, date(2026, 10, 4), signals)
        assert result["outcome"] == "filled"
        assert len(result["sessions"]) == 3  # catch-up of 3 missed sessions
        ledger = result and __import__(
            "niveshdristi.paper.ledger", fromlist=["PaperLedger"]
        ).PaperLedger(ledger_path)
        # candidates from created 10-01: 10-02, 10-03, 10-04 (3 catch-up)
        assert ledger.last_session_date() == date(2026, 10, 4)

    def test_zero_bars_is_non_session_noop(self, tmp_path):
        """A date with no valid bars is a NON-SESSION (honest substitute for
        the missing holiday list); never an invented holiday."""
        self._create(tmp_path)
        frames = self._frames(["2026-09-01"])  # only a PAST bar
        result = self._tick(tmp_path, frames, date(2026, 10, 2))
        assert result["outcome"] == "no-op"
        assert any("non-session (no valid bars)" in s for s in result["sessions"])

    def test_nan_bar_rejected_by_coverage(self, tmp_path):
        """A NaN-OHLC row (live-probe behavior) is NOT a valid bar: 1 of 2
        instruments valid -> coverage 0.5 < 0.6 default -> logged no-op."""
        self._create(tmp_path)
        bad = pl.DataFrame({
            "date": ["2026-10-02"], "close": [float("nan")], "volume": [1000],
        })
        good = pl.DataFrame({"date": ["2026-10-02"], "close": [100.0], "volume": [1000]})
        result = self._tick(
            tmp_path, {"SYN090": bad, "SYN091": good}, date(2026, 10, 2)
        )
        assert result["outcome"] == "no-op"
        assert any("insufficient coverage 1/2" in s for s in result["sessions"])

    def test_stale_data_noop(self, tmp_path):
        self._create(tmp_path)
        frames = self._frames(["2026-09-01"])  # far older than the candidate
        result = self._tick(tmp_path, frames, date(2026, 10, 20))
        assert result["outcome"] == "no-op"
        assert any("non-session" in s or "stale" in s for s in result["sessions"])

    def test_fetch_failure_no_state_change_no_halt(self, tmp_path):
        ledger_path = self._create(tmp_path)
        before = ledger_path.read_bytes()

        def failing_fetch(u, d):
            raise ConnectionError("provider down")

        result = self._tick(tmp_path, {}, date(2026, 10, 2), fetch=failing_fetch)
        assert result["outcome"] == "failure"
        assert "provider chain exhausted" in result["reason"]
        assert not (tmp_path / "paper_test" / "halt.flag").exists()  # no halt
        assert ledger_path.read_bytes() == before  # no state change

    def test_cache_ledger_mismatch_raises_and_halts(self, tmp_path):
        """Amendment C2: cache-vs-ledger disagreement at tick start raises
        and HALTS — NEVER auto-repairs."""
        fund_dir = tmp_path / "paper_test"
        self._create(tmp_path)
        cache = fund_dir / "broker_cache.json"
        cache.write_text(json.dumps({
            "last_session": "2026-10-01", "cash": 1.0, "fills": [{"bogus": True}] * 5,
        }), encoding="utf-8")
        frames = self._frames(["2026-10-01", "2026-10-02"])
        result = self._tick(
            tmp_path, frames, date(2026, 10, 2),
            signals={"2026-10-01": 1.0, "2026-10-02": 1.0},
        )
        assert result["outcome"] == "failure"
        assert "recover" in result["reason"]
        assert (fund_dir / "halt.flag").exists()  # halted by the tick driver

    @staticmethod
    def _tick(tmp_path, frames, clock_now, signals=None, fund_id="paper_test",
              fetch=None, models=None):
        from niveshdristi.engine.advance import ModelBundle as MB

        bundle = models or MB([TestAdvance._model(signals or {})])
        return tick(
            fund_id, base=tmp_path, fetch_bars=fetch or (lambda u, d: frames),
            clock_now=clock_now,
            models=bundle,
            rules=TestRiskGates._rules(), limits=TestPaperFund._limits(),
            rebalance=RebalanceSchedule(), universe=["SYN090", "SYN091"],
        )


class TestReplayByteEquality:
    """P6-S5: the C5 done-when — replay equals the ledger records."""

    @staticmethod
    def _seed_and_tick(tmp_path, days=3):
        # created the day BEFORE the first data session, so the paper
        # pipeline assesses from the same first session as a backtest over
        # the same frames (R7 SPEC TEST 3 alignment).
        ledger_path = TestPaperFund._create(tmp_path, created=date(2026, 9, 30))
        dates = [
            (date(2026, 10, 1) + timedelta(days=i)).isoformat() for i in range(days)
        ]
        c = [100.0 + 5.0 * ((i * 13) % 7) / 7 for i in range(len(dates))]
        common = {
            "date": dates, "close": c, "high": [v * 1.01 for v in c],
            "low": [v * 0.99 for v in c], "adj_close": c,
            "adj_high": [v * 1.01 for v in c], "adj_low": [v * 0.99 for v in c],
            "volume": [1_000_000] * len(dates),
        }
        frames = {"SYN090": pl.DataFrame(common), "SYN091": pl.DataFrame(common)}
        signals = {d: 0.5 + 0.1 * (i % 2) for i, d in enumerate(dates)}

        bundle = ModelBundle([TestAdvance._model(signals)])
        result = TestPaperFund._tick(
            tmp_path, frames, date(2026, 10, days), signals, models=bundle
        )
        return result, frames, ledger_path, bundle

    @staticmethod
    def _synth_bundle():
        """The SAME synthetic model bundle the tick used (rebuilt from the
        same signals — deterministic)."""
        from datetime import timedelta as _td

        from tests.test_advance import TestAdvance

        dates = [
            (date(2026, 10, 1) + _td(days=i)).isoformat() for i in range(3)
        ]
        signals = {d: 0.5 + 0.1 * (i % 2) for i, d in enumerate(dates)}
        return ModelBundle([TestAdvance._model(signals)])

    @staticmethod
    def _limits_v1():
        return GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0)

    def test_replay_byte_identical(self, tmp_path):
        from niveshdristi.paper.replay import replay_fund

        self._seed_and_tick(tmp_path, days=3)
        result = replay_fund(
            "paper_test", base=tmp_path,
            models=self._synth_bundle(), limits=self._limits_v1(),
            rebalance=RebalanceSchedule(),
        )
        assert result["byte_identical"] is True
        for entry in result["sessions"]:
            assert entry["match"] is True

    def test_replay_detects_snapshot_tampering(self, tmp_path):
        """A tampered snapshot breaks byte equality (the ledger stays right)."""
        from niveshdristi.engine.advance import RebalanceSchedule
        from niveshdristi.paper.replay import replay_fund

        self._seed_and_tick(tmp_path, days=3)
        snaps = tmp_path / "paper_test" / "snapshots"
        # The LAST session: a position exists there and is marked to market
        # on close. Tampering the FIRST session's snapshot would be vacuous
        # (no position yet, and the synthetic models ignore frame content),
        # so the record hash could not feel it.
        target = sorted(snaps.rglob("SYN090_*.parquet"))[-1]
        tampered = pl.read_parquet(target)
        tampered = tampered.with_columns(pl.lit(999.0).alias("close"))
        tampered.write_parquet(target)
        result = replay_fund(
            "paper_test", base=tmp_path,
            models=self._synth_bundle(), limits=self._limits_v1(),
            rebalance=RebalanceSchedule(),
        )
        assert result["byte_identical"] is False
        assert any(e.get("match") is False for e in result["sessions"])

    @staticmethod
    def _replay(tmp_path):
        from niveshdristi.paper.replay import replay_fund

        return replay_fund(
            "paper_test", base=tmp_path,
            models=TestReplayByteEquality._synth_bundle(),
            limits=TestReplayByteEquality._limits_v1(),
            rebalance=RebalanceSchedule(),
        )

    def test_replay_across_hash_seeds(self, tmp_path):
        """PYTHONHASHSEED variant: replay in a subprocess with a different
        hash seed still matches the ledger."""


        # each subprocess replays its OWN seeded copy (fresh fund per run)
        self._seed_and_tick(tmp_path / "seed3", days=3)
        self._seed_and_tick(tmp_path / "seed777", days=3)
        script = (
            "import sys, json; "
            "sys.path.insert(0, 'src'); sys.path.insert(0, 'tests'); "
            "from tests.test_paper import TestReplayByteEquality; "
            "r = TestReplayByteEquality._replay(tmp_path=sys.argv[1]); "
            "print(json.dumps({'byte_identical': r['byte_identical']}))"
        )
        outputs = []
        for seed in ("3", "777"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script, str(tmp_path / f"seed{seed}")],
                capture_output=True, text=True, env=env, timeout=240,
            )
            assert proc.returncode == 0, proc.stderr
            outputs.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        assert outputs[0] == outputs[1] == {"byte_identical": True}


def _backtest_matches_paper(tmp_path) -> dict:
    """R7 SPEC TEST 3 helper: run run_backtest on the SAME stored frames and
    configuration as the paper fund (same synthetic models, rules, limits,
    rebalance, initial cash, broker construction, tax_enabled=False) and
    compare every SessionRecord one by one with the paper ledger — hash and
    canonical bytes. Module-level so a subprocess can call it."""
    from niveshdristi.core.session import SessionRecord
    from niveshdristi.engine.backtest import run_backtest
    from niveshdristi.execution.sim_broker import SimBroker
    from niveshdristi.paper.ledger import PaperLedger

    result, frames, ledger_path, bundle = TestReplayByteEquality._seed_and_tick(
        tmp_path, days=3
    )
    rules = TestRiskGates._rules()
    bt = run_backtest(
        frames, models=bundle, rules=rules,
        limits=TestPaperFund._limits(), rebalance=RebalanceSchedule(),
        initial_cash=1_000_000.0, tax_enabled=False,
        broker=SimBroker(rates=rules.rates, price_limits=rules.price_limits),
    )
    stored = PaperLedger(ledger_path).records()
    # The backtest covers the full data calendar (including the fund's
    # created date); the paper period starts the day AFTER created. The
    # SPEC comparison is over the PAPER PERIOD: match backtest records by
    # session_date and require every paper record to have a twin.
    by_date = {r.session_date.isoformat(): r for r in bt.records}
    mismatches: list[dict] = []
    for i, line in enumerate(stored):
        b = by_date.get(line["session_date"])
        if b is None:
            return {"identical": False,
                    "reason": f"no backtest record for {line['session_date']}"}
        rec = SessionRecord.model_validate(
            {k: v for k, v in line.items() if k != "hash"}
        )
        same_hash = b.compute_hash() == line["hash"]
        same_bytes = (
            json.dumps(b._canonical(), sort_keys=True, default=str)
            == json.dumps(rec._canonical(), sort_keys=True, default=str)
        )
        if not (same_hash and same_bytes):
            mismatches.append({"i": i, "same_hash": same_hash, "same_bytes": same_bytes})
    return {"identical": not mismatches, "mismatches": mismatches,
            "sessions": len(stored)}


class TestBacktestPaperEquality:
    """R7 SPEC TESTS 3+4: replay of a past period equals the BACKTEST
    records for the same period, hash and canonical bytes, one by one."""

    def test_backtest_records_equal_paper_ledger(self, tmp_path):
        result = _backtest_matches_paper(tmp_path)
        assert result["identical"] is True, result
        assert result["sessions"] > 0

    def test_backtest_paper_equality_across_hash_seeds(self, tmp_path):
        """R7 SPEC TEST 4: the same comparison in a subprocess under two
        different PYTHONHASHSEED values."""
        script = (
            "import sys, json; "
            "sys.path.insert(0, 'src'); sys.path.insert(0, '.'); "
            "from tests.test_paper import _backtest_matches_paper; "
            "print(json.dumps(_backtest_matches_paper(sys.argv[1])))"
        )
        outputs = []
        for seed in ("3", "777"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script, str(tmp_path / f"seed{seed}")],
                capture_output=True, text=True, env=env, timeout=240,
            )
            assert proc.returncode == 0, proc.stderr
            outputs.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        assert outputs[0] == outputs[1]
        assert outputs[0]["identical"] is True, outputs
