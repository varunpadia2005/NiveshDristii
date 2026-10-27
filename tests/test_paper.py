"""P6-S2 tests: paper fund lifecycle, commit protocol, lock, tick semantics.

All frames are synthetic (SYN names, generated in code). Tests always pass
tmp_path as the fund base (amendment D) — the default location is never
written. No clock reads: the candidate date is an explicit argument.
"""

import json
from datetime import date
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
    def _create(tmp_path, fund_id="paper_test"):
        return create_fund(
            fund_id, base=tmp_path, created=date(2026, 10, 1),
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

    def _tick(self, tmp_path, frames, clock_now, signals=None, fund_id="paper_test",
              fetch=None):
        return tick(
            fund_id, base=tmp_path, fetch_bars=fetch or (lambda u, d: frames),
            clock_now=clock_now,
            models=ModelBundle([TestAdvance._model(signals or {})]),
            rules=TestRiskGates._rules(), limits=self._limits(),
            rebalance=RebalanceSchedule(), universe=["SYN090", "SYN091"],
        )
