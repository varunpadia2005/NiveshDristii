"""P6-S3 tests: kill switch, events log + injected clock, heartbeat,
notifier interface. All NEW; fake clock injected (no real clock reads in
paper/ outside the injected one)."""

import json
from datetime import UTC, date, datetime

import pytest

from niveshdristi.core.errors import KillSwitchError
from niveshdristi.paper.events import EventLog, write_heartbeat
from niveshdristi.paper.killswitch import halt, is_halted, resume
from niveshdristi.paper.notifier import LogOnlyNotifier, NullNotifier, default_notifier


class TestKillSwitch:
    def test_halt_and_is_halted(self, tmp_path):
        payload = halt(
            tmp_path, fund_id="f1", reason="model exception",
            session=date(2026, 10, 23), event_id="e1",
        )
        assert payload["fund_id"] == "f1"
        halted, reason = is_halted(tmp_path, fund_id="f1")
        assert halted
        assert reason == "model exception"

    def test_resume_requires_note(self, tmp_path):
        halt(tmp_path, fund_id="f1", reason="r", session=date(2026, 10, 23), event_id="e1")
        with pytest.raises(KillSwitchError, match="non-empty note"):
            resume(tmp_path, note="")
        resume(tmp_path, note="investigated; resuming")
        assert not (tmp_path / "halt.flag").exists()

    def test_resume_not_halted_is_error(self, tmp_path):
        with pytest.raises(KillSwitchError, match="not halted"):
            resume(tmp_path, note="nothing to resume")

    def test_corrupt_flag_is_fail_safe_halted(self, tmp_path):
        (tmp_path / "halt.flag").write_text("not json {{{", encoding="utf-8")
        halted, reason = is_halted(tmp_path, fund_id="f1")
        assert halted
        assert "UNREADABLE" in reason

    def test_mismatched_flag_is_fail_safe_halted(self, tmp_path):
        halt(tmp_path, fund_id="OTHER", reason="r", session=date(2026, 10, 23), event_id="e")
        halted, reason = is_halted(tmp_path, fund_id="f1")
        assert halted
        assert "MISMATCH" in reason

    def test_exception_in_model_halts_and_appends_nothing(self, tmp_path):
        """Amendment F: an exception during the tick halts the fund and NO
        ledger line is appended (the ledger write is after compute)."""
        from niveshdristi.engine.advance import ModelBundle
        from niveshdristi.paper.fund import tick
        from tests.test_advance import TestAdvance, TestRiskGates
        from tests.test_paper import TestPaperFund

        TestPaperFund._create(tmp_path)

        class ExplodingModel:
            model_id = "boom"

            def predict(self, ctx, inputs):
                raise RuntimeError("model exploded")

        import polars as pl

        frames = {
            "SYN090": pl.DataFrame({
                "date": ["2026-10-02"], "close": [100.0], "volume": [1000],
            }),
            "SYN091": pl.DataFrame({
                "date": ["2026-10-02"], "close": [100.0], "volume": [1000],
            }),
        }
        ledger_path = tmp_path / "paper_test" / "ledger.jsonl"
        before = ledger_path.read_bytes()
        with pytest.raises(RuntimeError, match="model exploded"):
            tick(
                "paper_test", base=tmp_path, fetch_bars=lambda u, d: frames,
                clock_now=date(2026, 10, 2),
                models=ModelBundle([ExplodingModel()]),
                rules=TestRiskGates._rules(),
                limits=TestPaperFund._limits(),
                rebalance=TestAdvance.RebalanceSchedule()
                if hasattr(TestAdvance, "RebalanceSchedule")
                else __import__(
                    "niveshdristi.engine.advance", fromlist=["RebalanceSchedule"]
                ).RebalanceSchedule(),
                universe=["SYN090", "SYN091"],
            )
        # the tick driver's caller (CLI in S4) writes the flag; here we
        # verify the ledger was NOT appended (exception before the write)
        assert ledger_path.read_bytes() == before


class TestEventLogAndHeartbeat:
    def test_events_append_and_read_with_injected_clock(self, tmp_path):
        """Wall-clock timestamps come ONLY from the INJECTED clock (G08 stays
        green: no clock reads in paper/ code paths under test)."""
        fake_times = iter(
            [datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
             datetime(2026, 10, 24, 18, 0, tzinfo=UTC)]
        )

        def fake_clock():
            return next(fake_times)

        log = EventLog(tmp_path / "events.jsonl", clock=fake_clock)
        log.append("tick", fund_id="f1", outcome="filled")
        log.append("no-op", fund_id="f1", reason="idempotent")
        events = log.read()
        assert len(events) == 2
        assert events[0]["timestamp"] == "2026-10-23T18:00:00+00:00"
        assert events[0]["event"] == "tick"
        assert events[1]["timestamp"] == "2026-10-24T18:00:00+00:00"

    def test_events_file_is_jsonl_one_object_per_line(self, tmp_path):
        log = EventLog(tmp_path / "events.jsonl")
        log.append("halt", fund_id="f1")
        log.append("resume", fund_id="f1")
        raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
        lines = raw.splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "halt"
        assert json.loads(lines[1])["event"] == "resume"

    def test_heartbeat_updated_on_every_tick_including_noops(self, tmp_path):
        fake = iter([datetime(2026, 10, 23, 18, 0, tzinfo=UTC)] * 3)

        def fake_clock():
            return next(fake)

        hb = tmp_path / "heartbeat.json"
        write_heartbeat(hb, clock=fake_clock, fund_id="f1", last_tick="filled")
        data = json.loads(hb.read_text(encoding="utf-8"))
        assert data["fund_id"] == "f1"
        write_heartbeat(hb, clock=fake_clock, fund_id="f1", last_tick="no-op")
        data = json.loads(hb.read_text(encoding="utf-8"))
        assert data["last_tick"] == "no-op"  # no-ops also update it


class TestNotifier:
    def test_null_notifier_default_off(self):
        notifier = default_notifier()
        assert isinstance(notifier, NullNotifier)
        notifier.notify("anything", {})  # no error, no side effect

    def test_log_only_notifier_delegates(self):
        seen = []

        def sink(event, payload):
            seen.append((event, payload))

        notifier = LogOnlyNotifier(sink)
        notifier.notify("halt", {"reason": "r"})
        assert seen == [("halt", {"reason": "r"})]

    def test_log_only_rejects_non_callable(self):
        from niveshdristi.core.errors import ConfigurationError

        with pytest.raises(ConfigurationError, match="callable"):
            LogOnlyNotifier("not callable")

    def test_no_network_notifier_exists(self):
        """Amendment H: NO Telegram/email/network notifier in Phase 6. The
        module exposes exactly Null and LogOnly implementations."""
        import niveshdristi.paper.notifier as mod

        public = [n for n in dir(mod) if n.endswith("Notifier")]
        assert sorted(public) == ["LogOnlyNotifier", "Notifier", "NullNotifier"]
