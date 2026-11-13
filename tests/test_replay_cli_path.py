"""FX-N (fix run 5): replay byte-identity on the CLI path and the demo
generator — the C5 done-when extended to funds created OUTSIDE tests.

ROOT CAUSES (R2 diagnosis; raw repro output in fix5_evidence.txt):
- RC1: the demo generator recorded the DEFAULT GateLimits digest but
  ticked with permissive limits; compose_from_recorded could only
  rebuild defaults -> different gated weights -> 5x larger fills from
  the first pending execution (2026-10-25 in the demo ledger).
- RC2: _rebuild_state's gross shadow walk skipped the per-session
  snap() that advance() applies at every session end -> a one-paise
  gross_equity_after drift across every tick boundary, visible from the
  first session that executes a pending created in a PREVIOUS tick
  invocation (per-day ticks, the operator loop).

The tests run the REAL CLI commands (typer CliRunner) with a
REAL-WINDOW fake provider (honors the start_window the CLI derives),
one tick invocation per session day — the operator loop — and assert
the replay is byte-identical. NON-VACUITY: the ledger must contain
fills and several records (an empty/no-fill replay matches trivially
and proves nothing). The young fund also exercises the FX-I
insufficient_history event through the same CLI path.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from niveshdristi.cli.main import app

REPO = Path(__file__).resolve().parent.parent
runner = CliRunner()

END = "2026-10-02"
N_DAYS = 500
TICK_DATES = 8  # per-day tick invocations (the operator loop)


def _long_dates(end: str = END, n: int = N_DAYS) -> list[str]:
    from datetime import date as _d
    from datetime import timedelta

    end_date = _d.fromisoformat(end)
    return [
        (end_date - timedelta(days=n - 1 - i)).isoformat() for i in range(n)
    ]


def _fake_frames(dates: list[str]) -> dict[str, pl.DataFrame]:
    """Fake bars with BOTH close (price-level models) and adj_* (the
    ta_ensemble's legacy indicators consume adj_close/adj_high/adj_low)."""
    c = [100.0 + 15.0 * math.sin(i / 12.0) + i * 0.05 for i in range(len(dates))]
    common = {
        "date": dates, "close": c, "high": [v * 1.01 for v in c],
        "low": [v * 0.99 for v in c], "adj_close": c,
        "adj_high": [v * 1.01 for v in c], "adj_low": [v * 0.99 for v in c],
        "volume": [1_000_000] * len(dates),
    }
    return {"SYN090": pl.DataFrame(common), "SYN091": pl.DataFrame(common)}


@pytest.fixture
def real_window_provider(monkeypatch):
    """REAL-WINDOW fake provider: honors the start the CLI derives
    (start_window) and returns ONLY rows dated on or after it — the
    semantics of a real provider fetch, not a full-history dump."""
    full = _fake_frames(_long_dates())

    def fetch(universe, start, end):
        out: dict[str, pl.DataFrame] = {}
        for sym, frame in full.items():
            out[sym] = frame.filter(
                pl.col("date").cast(pl.String).str.slice(0, 10)
                >= start.isoformat()
            )
        return out

    monkeypatch.setattr("niveshdristi.cli.main._paper_fetch_bars", fetch)
    return full


def _ledger_records(base: Path, fund_id: str) -> list[dict]:
    lines = (base / fund_id / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()
    return [
        json.loads(x) for x in lines[1:] if x.strip()
    ]


def _total_fills(records: list[dict]) -> int:
    return sum(len(r.get("fills", [])) for r in records)


class TestReplayCliPath:
    def test_cli_created_fund_per_day_ticks_replay_byte_identical(
        self, tmp_path, real_window_provider
    ):
        """SPEC (fix run 5, headline 1): a CLI-created fund, ticked ONE
        INVOCATION PER DAY (the operator loop, cache round-trip between
        ticks), replays byte-identical from its stored snapshots."""
        dates = _long_dates()
        created = dates[len(dates) - TICK_DATES - 1]
        r = runner.invoke(
            app, ["--json", "paper", "create", "pf_replay",
                  "--created", created,
                  "--universe", "SYN090,SYN091", "--base", str(tmp_path)]
        )
        assert r.exit_code == 0, r.output
        for day in dates[len(dates) - TICK_DATES:]:
            rt = runner.invoke(
                app, ["--json", "paper", "tick", "pf_replay",
                      "--as-of", day, "--base", str(tmp_path)]
            )
            assert rt.exit_code == 0, rt.output
            assert json.loads(rt.output)["status"] == "filled"
        records = _ledger_records(tmp_path, "pf_replay")
        # NON-VACUITY: several records AND real fills — a trivial
        # empty/no-fill replay would match and prove nothing.
        assert len(records) == TICK_DATES
        assert _total_fills(records) >= 1
        rr = runner.invoke(
            app, ["--json", "paper", "replay", "pf_replay",
                  "--base", str(tmp_path)]
        )
        assert rr.exit_code == 0, rr.output
        data = json.loads(rr.output)
        assert data["composition_recorded"] is True
        assert data["byte_identical"] is True, data
        assert all(s["match"] is True for s in data["sessions"])
        assert len(data["sessions"]) == TICK_DATES

    def test_young_fund_emits_insufficient_history_and_warming_up(
        self, tmp_path, real_window_provider
    ):
        """FX-I through the SAME CLI path: a fund with fewer ticked
        sessions than its composition's required history emits
        insufficient_history events and reports warming_up in status."""
        dates = _long_dates()
        created = dates[len(dates) - TICK_DATES - 1]
        runner.invoke(
            app, ["--json", "paper", "create", "pf_young",
                  "--created", created,
                  "--universe", "SYN090,SYN091", "--base", str(tmp_path)]
        )
        for day in dates[len(dates) - TICK_DATES:]:
            runner.invoke(
                app, ["--json", "paper", "tick", "pf_young",
                      "--as-of", day, "--base", str(tmp_path)]
            )
        events = (tmp_path / "pf_young" / "events.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert any("insufficient_history" in e for e in events)
        rs = runner.invoke(
            app, ["--json", "paper", "status", "pf_young",
                  "--base", str(tmp_path)]
        )
        status = json.loads(rs.output)
        assert status["warming_up"] is not None
        assert status["warming_up"]["status"].startswith("warming up")

    def test_demo_fund_cli_replay_byte_identical(self, tmp_path):
        """SPEC (fix run 5, headline 2): the demo generator builds through
        the SAME composition path (it records the limits it ticks with)
        and the CLI replay of the generated fund is byte-identical."""
        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO, timeout=900,
        )
        assert proc.returncode == 0, proc.stderr[-400:]
        records = _ledger_records(tmp_path, "demo_synthetic")
        assert len(records) == 8
        # NON-VACUITY: the demo ledger carries real fills
        assert _total_fills(records) >= 1
        rr = runner.invoke(
            app, ["--json", "paper", "replay", "demo_synthetic",
                  "--base", str(tmp_path)]
        )
        assert rr.exit_code == 0, rr.output
        data = json.loads(rr.output)
        assert data["composition_recorded"] is True
        assert data["byte_identical"] is True, data
        assert all(s["match"] is True for s in data["sessions"])
        assert len(data["sessions"]) == 8
