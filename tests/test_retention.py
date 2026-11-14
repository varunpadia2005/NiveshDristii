"""P10-S6 (D7): snapshot pruning + events rotation — retention with an
explicit replay trade-off."""

from __future__ import annotations

import json
from datetime import date, timedelta

from niveshdristi.paper.events import EventLog
from niveshdristi.paper.retention import prune_snapshots


class TestSnapshotPruning:
    @staticmethod
    def _seeded(tmp_path, days=5):
        from tests.test_paper import TestPaperFund

        frames_path = "tests.test_paper"
        frames = __import__(frames_path, fromlist=["_momentum_frames"]) \
            ._momentum_frames(days)
        dates = sorted(frames["SYN090"]["date"].to_list())
        TestPaperFund._create(
            tmp_path,
            created=date.fromisoformat(dates[0]) - timedelta(days=1))
        for d in dates:
            TestPaperFund._tick(
                tmp_path, frames, date.fromisoformat(d), None)
        return tmp_path, dates

    def test_dry_run_default_deletes_nothing(self, tmp_path):
        tmp_path, dates = self._seeded(tmp_path)
        snaps = tmp_path / "paper_test" / "snapshots"
        before = sorted(p.name for p in snaps.iterdir())
        result = prune_snapshots("paper_test", tmp_path, keep_last=2)
        assert result["applied"] is False
        assert len(result["prunable"]) == len(before) - 2
        assert sorted(p.name for p in snaps.iterdir()) == before

    def test_apply_deletes_only_old_snapshot_dirs(self, tmp_path):
        tmp_path, dates = self._seeded(tmp_path)
        snaps = tmp_path / "paper_test" / "snapshots"
        result = prune_snapshots("paper_test", tmp_path, keep_last=2,
                                 apply=True)
        assert result["applied"] is True
        remaining = sorted(p.name for p in snaps.iterdir())
        assert remaining == sorted(dates[-2:])
        # NEVER touched: ledger, sidecars, halt, heartbeat, cache
        fund = tmp_path / "paper_test"
        assert (fund / "ledger.jsonl").exists()
        assert (fund / "decisions").exists()
        assert (fund / "events.jsonl").exists()

    def test_replay_reports_pruned_sessions_explicitly(self, tmp_path):
        from tests.test_paper import TestReplayByteEquality

        tmp_path, _ = self._seeded(tmp_path)
        prune_snapshots("paper_test", tmp_path, keep_last=1, apply=True)
        replay = TestReplayByteEquality._replay(tmp_path)
        pruned = [e for e in replay["sessions"] if e["match"] is None]
        assert pruned, "pruned sessions must be explicitly reported"
        assert all("snapshots unavailable" in e["note"] for e in pruned)
        assert replay["byte_identical"] is False  # NOT a silent pass


class TestEventsRotation:
    def test_rotation_at_threshold_keeps_one_generation(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl",
                       rotation_threshold_bytes=200)
        for i in range(10):
            log.append("tick", i=i, pad="x" * 40)
        assert log.path.exists()
        rotated = tmp_path / "events.jsonl.1"
        assert rotated.exists(), "rotation must have fired"
        assert log.path.stat().st_size <= 200 + 120  # last events only
        # multi-rotation contract: .1 holds the PREVIOUS live generation
        # (overwritten on each rotation); the live file holds the newest
        live_lines = log.path.read_text(encoding="utf-8").splitlines()
        assert '"i": 9' in live_lines[-1]  # newest event in the live file

    def test_no_rotation_below_threshold(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl",
                       rotation_threshold_bytes=10_000_000)
        log.append("tick", i=0)
        assert not (tmp_path / "events.jsonl.1").exists()


class TestInsufficientHistoryFXI:
    """FX-I 3: a provider returning 30 sessions yields the
    insufficient_history event, status shows "warming up", no crash."""

    def test_insufficient_history_event(self, tmp_path):
        from typer.testing import CliRunner

        import niveshdristi.cli.main as cm
        from niveshdristi.cli.main import app
        from tests.test_paper_cli import _fake_frames, _long_dates

        # 30-session provider (insufficient for the 200-session TaEnsemble)
        frames = _fake_frames(_long_dates(n=30))
        cm._paper_fetch_bars = lambda u, s, e: frames
        runner = CliRunner()
        base = tmp_path / "funds"

        r = runner.invoke(app, ["--json", "paper", "create", "short_f",
                                "--base", str(base), "--created", "2026-09-29",
                                "--universe", "SYN090,SYN091"])
        assert r.exit_code == 0
        r = runner.invoke(app, ["--json", "paper", "tick", "short_f",
                                "--as-of", "2026-10-30", "--base", str(base)])
        assert r.exit_code == 0  # no crash, no halt
        # the insufficient_history event should be in events.jsonl
        events_file = base / "short_f" / "events.jsonl"
        events = [json.loads(x) for x in
                  events_file.read_text(encoding="utf-8").splitlines()
                  if x.strip()]
        insuff = [e for e in events if e.get("event") == "insufficient_history"]
        assert insuff, "insufficient_history event not found"
        assert any(m["model_id"] == "ta_ensemble" for m in insuff[0]["models"])

    def test_warming_up_status(self, tmp_path):
        from typer.testing import CliRunner

        import niveshdristi.cli.main as cm
        from niveshdristi.cli.main import app
        from tests.test_paper_cli import _fake_frames, _long_dates

        frames = _fake_frames(_long_dates(n=30))
        cm._paper_fetch_bars = lambda u, s, e: frames
        runner = CliRunner()
        base = tmp_path / "funds"
        runner.invoke(app, ["--json", "paper", "create", "short_f",
                            "--base", str(base), "--created", "2026-09-29",
                            "--universe", "SYN090,SYN091"])
        runner.invoke(app, ["--json", "paper", "tick", "short_f",
                            "--as-of", "2026-10-30", "--base", str(base)])
        r = runner.invoke(app, ["--json", "paper", "status", "short_f",
                                "--base", str(base)])
        assert r.exit_code == 0
        d = json.loads(r.output)
        assert d.get("warming_up"), "status should show warming_up"
