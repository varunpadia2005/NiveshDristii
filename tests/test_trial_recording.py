"""P11-S4: TrialRecorder wiring at the CALLER (services/backtest_lab).

Phase 6's need — "TrialRecorder integration into every real backtest
run" — is wired at the services/ composition point (NEVER inside
engine/): every successful run_backtest_service call records ONE trial
(idempotent by content key: re-running identical content does not
inflate the trial count), and the result reports the recorder's
cumulative trial_count as `trials_recorded`.

Non-vacuity: the recorded trial's net-return series is derived from the
backtest's net equity curve (rows > 0 asserted via the recorder trial).
Both markets: the IN run records; the US run records AND still carries
costs_not_modeled + the COSTS NOT MODELED banner.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _seeded_fund(tmp_path: Path, fund_id: str = "paper_test") -> tuple:
    """A small deterministic paper fund (same pattern as test_ui's
    TestBacktestLabS8._seeded), ticked to dates[9]."""
    from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

    frames = _momentum_frames(12)
    dates = _momentum_session_dates(frames)
    TestPaperFund._create(
        tmp_path, fund_id=fund_id,
        created=date.fromisoformat(dates[0]) - timedelta(days=1))
    TestPaperFund._tick(
        tmp_path, frames, date.fromisoformat(dates[9]), None, fund_id=fund_id)
    return frames, dates


class TestTrialRecordingP11:
    def test_service_run_records_trial_and_increments(self, tmp_path):
        from niveshdristi.services.backtest_lab import (
            content_key,
            run_backtest_service,
        )

        frames, dates = _seeded_fund(tmp_path, "paper_trial")
        key1 = content_key("paper_trial", tmp_path)
        r1 = run_backtest_service("paper_trial", tmp_path, _key=key1)
        assert r1["available"] is True, r1
        n1 = r1["trials_recorded"]
        assert n1 >= 1, "first real backtest run must record a trial"
        # non-vacuity at the recorder level: the trial carries a
        # multi-point net-return series derived from the equity curve
        from niveshdristi.services.backtest_lab import recorded_trials

        trials = recorded_trials()
        assert trials, "the module recorder must expose recorded trials"
        assert any(len(t.net_returns) > 1 for t in trials), (
            "a recorded trial must carry a multi-session return series"
        )

        # a SECOND run over MORE content (one more ticked session) must
        # increment the recorded trial count
        from tests.test_paper import TestPaperFund

        TestPaperFund._tick(
            tmp_path, frames, date.fromisoformat(dates[10]), None,
            fund_id="paper_trial")
        key2 = content_key("paper_trial", tmp_path)
        assert key2 != key1, "the content key must change with new data"
        r2 = run_backtest_service("paper_trial", tmp_path, _key=key2)
        assert r2["available"] is True, r2
        assert r2["trials_recorded"] == n1 + 1, (
            "a second run over different content must increment the "
            "recorded trial count"
        )

    def test_identical_content_does_not_inflate_trials(self, tmp_path):
        from niveshdristi.services.backtest_lab import (
            content_key,
            run_backtest_service,
        )

        _seeded_fund(tmp_path, "paper_idem")
        key = content_key("paper_idem", tmp_path)
        r1 = run_backtest_service("paper_idem", tmp_path, _key=key)
        n1 = r1["trials_recorded"]
        r2 = run_backtest_service("paper_idem", tmp_path, _key=key)
        assert r2["trials_recorded"] == n1, (
            "re-running IDENTICAL content must not inflate the trial "
            "count (duplicate trials are statistically dishonest)"
        )

    def test_us_run_records_trial_and_keeps_costs_flag(self, tmp_path):
        from niveshdristi.services.backtest_lab import (
            content_key,
            run_backtest_service,
        )

        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(tmp_path),
             "--fund-id", "trial_us", "--market", "US_NYSE"],
            capture_output=True, text=True, cwd=REPO, timeout=900,
        )
        assert proc.returncode == 0, proc.stderr[-300:]
        key = content_key("trial_us", tmp_path)
        r = run_backtest_service("trial_us", tmp_path, _key=key)
        assert r["available"] is True, r
        assert r["trials_recorded"] >= 1
        assert "costs_not_modeled" in r["limitations"], r
        assert "COSTS NOT MODELED" in (r.get("banner") or ""), r
