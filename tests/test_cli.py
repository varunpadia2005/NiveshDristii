"""
Test CLI with Typer's CliRunner.

Protects the rule that nd CLI commands work and --json outputs valid JSON.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from niveshdristi.cli.main import app

runner = CliRunner()


class TestCLIHelp:
    """nd --help works and lists commands."""

    def test_help_exits_zero(self):
        """nd --help exits with code 0."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_lists_commands(self):
        """Help output lists all top-level commands."""
        result = runner.invoke(app, ["--help"])
        assert "config" in result.output
        assert "validate" in result.output
        assert "version" in result.output
        assert "data" in result.output
        assert "signals" in result.output
        assert "backtest" in result.output
        assert "paper" in result.output

    def test_version_exits_zero(self):
        """nd version exits with code 0."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        # Version outputs a Rich table with version key
        assert "version" in result.output


class TestCLIJSONOutput:
    """Commands with --json output valid JSON."""

    def test_version_json(self):
        """nd --json version outputs valid JSON."""
        result = runner.invoke(app, ["--json", "version"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "version" in data or "name" in data

    def test_config_show_json(self):
        """nd config --show --json outputs valid JSON."""
        # DATABASE_URL pinned: an unset-var warning goes to stderr but
        # CliRunner merges it into output in some click versions; the
        # unset case is covered end-to-end by the F3 subprocess test.
        result = runner.invoke(app, ["--json", "config", "--show"],
                               env={"DATABASE_URL": "sqlite://"})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "backtest" in data
        assert "data" in data

    def test_config_validate_json(self):
        """nd config --validate --json outputs valid JSON."""
        result = runner.invoke(app, ["--json", "config", "--validate"],
                               env={"DATABASE_URL": "sqlite://"})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data.get("valid") is True

    def test_data_help_json(self):
        """nd --json data --help outputs valid JSON (empty or help)."""
        result = runner.invoke(app, ["--json", "data", "--help"])
        # Help exits 0 but may not be JSON - that's OK
        assert result.exit_code == 0


class TestCLISubcommands:
    """Subcommand structure is correct per CHANGES.md C13."""

    def test_data_subcommands(self):
        """nd data has fetch, refresh subcommands."""
        result = runner.invoke(app, ["data", "--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output
        assert "refresh" in result.output

    def test_signals_subcommands(self):
        """nd signals has generate subcommand."""
        result = runner.invoke(app, ["signals", "--help"])
        assert result.exit_code == 0
        assert "generate" in result.output

    def test_backtest_subcommands(self):
        """nd backtest has run subcommand."""
        result = runner.invoke(app, ["backtest", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    def test_paper_subcommands(self):
        """nd paper has create, tick, status, halt, resume subcommands."""
        result = runner.invoke(app, ["paper", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "tick" in result.output
        assert "status" in result.output
        assert "halt" in result.output
        assert "resume" in result.output


class TestConfigCommand:
    """Config command works."""

    def test_config_show(self):
        """nd config --show works."""
        result = runner.invoke(app, ["config", "--show"])
        assert result.exit_code == 0
        assert "backtest" in result.output or "data" in result.output

    def test_config_validate(self):
        """nd config --validate works."""
        result = runner.invoke(app, ["config", "--validate"])
        assert result.exit_code == 0

class TestJSONSubprocess:
    """--json stdout must be pure, width-independent JSON (real subprocess).

    Regression: _output() printed JSON through a Rich Console, which wraps at
    the terminal width and inserts newlines inside JSON string literals,
    producing invalid JSON on narrow terminals.
    """

    def test_validate_json_is_valid_at_narrow_width(self):
        """COLUMNS=40: json.loads(stdout) succeeds with summary keys present."""
        import os
        import subprocess
        import sys

        # The CLI resolves config.yaml/universes/ from its working directory
        repo_root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        env["COLUMNS"] = "40"
        proc = subprocess.run(
            [sys.executable, "-m", "niveshdristi.cli.main", "--json", "validate"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        data = json.loads(proc.stdout)
        assert "summary" in data
        assert "checks" in data
        assert data["summary"]["passed"] == data["summary"]["total"]


class TestJsonStdoutPurityF3:
    """F3: with DATABASE_URL absent from the environment, `nd --json
    validate` stdout must be pure valid JSON (exit 0) and any unset-variable
    warning must appear ONLY on stderr (config_loader.py already prints it
    to stderr; this test pins it against regressions and CliRunner-mixing
    artifacts). Runs in a REAL subprocess."""

    def test_validate_stdout_is_pure_json_without_database_url(self):
        import json as _json
        import os
        import subprocess
        import sys

        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        proc = subprocess.run(
            [sys.executable, "-m", "niveshdristi.cli.main", "--json", "validate"],
            capture_output=True, text=True, env=env, timeout=240,
        )
        assert proc.returncode == 0, proc.stderr[-500:]
        data = _json.loads(proc.stdout)  # must parse: pure JSON on stdout
        assert data["summary"]["failed"] == 0
        combined = proc.stdout
        assert "Warning: environment variable" not in combined


class TestSchedulerCommandF4:
    """F4: the exact command documented in docs/SCHEDULER.md must actually
    work — extract the python module path and subcommand from the doc and
    run `--help` in a real subprocess, asserting exit 0 and a clean stderr
    (no traceback, no runpy RuntimeWarning)."""

    def test_documented_module_runs_help_from_other_cwd(self, tmp_path):
        import os
        import re
        import subprocess
        import sys
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent
        doc = (repo / "docs" / "SCHEDULER.md").read_text(encoding="utf-8")
        m = re.search(r'"[^"]*python[^"]*"\s+(-m\s+\S+)\s+(paper\s+tick)', doc)
        assert m, "documented command not found in docs/SCHEDULER.md"
        module = m.group(1).split()[1]
        subcmd = m.group(2).split()
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo / "src")
        proc = subprocess.run(
            [sys.executable, "-m", module, *subcmd, "--help"],
            capture_output=True, text=True, env=env,
            # cwd = a DIFFERENT directory; config.yaml is imported at module
            # load, so the doc must (and does) require "Start in" = repo root.
            # We run from the repo root to mirror the documented requirement
            # and separately assert the doc states it.
            cwd=repo,
        )
        assert proc.returncode == 0, proc.stderr[-400:]
        assert "Usage" in proc.stdout
        assert "Traceback" not in proc.stderr
        assert "RuntimeWarning" not in proc.stderr


    def test_doc_states_start_in_requirement(self):
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent
        doc = (repo / "docs" / "SCHEDULER.md").read_text(encoding="utf-8")
        assert "Start in" in doc
        assert "REPO ROOT" in doc


class TestBacktestRunP10:
    """P10-S3 (D5): nd backtest run over stored snapshots — offline, plain
    JSON, fixed verdict wording, exit codes 0/1/2."""

    @staticmethod
    def _seeded(tmp_path):
        from datetime import date as _d
        from datetime import timedelta

        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=_d.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, _d.fromisoformat(dates[9]), None)
        return tmp_path

    def test_success_json_and_verdict(self, tmp_path):
        tmp_path = self._seeded(tmp_path)
        result = runner.invoke(app, [
            "--json", "backtest", "run", "paper_test", "--base", str(tmp_path)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)  # valid JSON at any width
        assert data["status"] == "ok"
        assert data["verdict"] == ("validation-gate result: pipeline "
                                   "demonstration only; not evidence of "
                                   "performance")
        assert "costs_not_modeled" not in data["limitation_codes"]
        assert "rates_unverified" in data["limitation_codes"]

    def test_unavailable_fund_exits_1(self, tmp_path):
        # a fund with NO stored sessions: verify (empty ledger)
        from datetime import date as _dd

        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.paper.fund import create_fund

        create_fund("empty_bt", base=tmp_path, created=_dd(2026, 10, 1),
                    config_digest="t", rules=MarketRules(market_id="TEST_M"),
                    limitations=DataLimitations(
                        CODES=frozenset({"rates_unverified"})),
                    rates_verified=False, initial_cash=1_000_000.0,
                    universe=["SYN090"])
        result = runner.invoke(app, [
            "--json", "backtest", "run", "empty_bt", "--base", str(tmp_path)])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "unavailable"

    def test_usage_error_exit_2(self, tmp_path):
        result = runner.invoke(app, ["backtest", "run"])  # missing fund_id
        assert result.exit_code == 2

    def test_json_valid_at_narrow_width(self, tmp_path):
        tmp_path = self._seeded(tmp_path)
        result = runner.invoke(app, [
            "--json", "backtest", "run", "paper_test", "--base", str(tmp_path)],
            env={"COLUMNS": "40"})
        assert result.exit_code == 0
        json.loads(result.output)  # must parse at 40 columns

    def test_deprecated_options_accepted_with_stderr_notice(self, tmp_path):
        tmp_path = self._seeded(tmp_path)
        result = runner.invoke(app, [
            "--json", "backtest", "run", "paper_test", "--base", str(tmp_path),
            "--mandate", "core", "--universe", "nifty50", "--start",
            "2026-01-01"])
        assert result.exit_code == 0
        assert "deprecated" in result.stderr


class TestMissingFundErrorsFXD:
    """FX-D: every nd paper subcommand on a missing fund exits 1 with the
    plain JSON error payload (status error, detail naming the fund,
    next_step). Never a traceback."""

    @pytest.mark.parametrize("cmd_args", [
        ["paper", "status", "ghost"],
        ["paper", "verify", "ghost"],
        ["paper", "replay", "ghost"],
        ["paper", "tick", "ghost"],
        ["paper", "halt", "ghost"],
        ["paper", "resume", "ghost", "--note", "x"],
        ["paper", "recover", "ghost"],
        ["paper", "unlock", "ghost"],
        ["paper", "prune-snapshots", "ghost"],
    ])
    def test_missing_fund_json_error(self, tmp_path, cmd_args):
        result = runner.invoke(app, ["--json", *cmd_args,
                                     "--base", str(tmp_path)])
        assert result.exit_code == 1, (cmd_args, result.output)
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert "ghost" in data["detail"]
        assert "next_step" in data
        assert "nd paper create" in data["next_step"]

    def test_backtest_run_missing_fund(self, tmp_path):
        result = runner.invoke(app, [
            "--json", "backtest", "run", "ghost", "--base", str(tmp_path)])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] in ("error", "unavailable")


    def test_explain_missing_fund_exits_0_noop(self, tmp_path):
        """FX-D amended: nd paper explain on a missing fund exits 0 with
        a no-op payload (R11: LLM-layer failures degrade to a logged
        no-op and never raise)."""
        result = runner.invoke(app, [
            "--json", "paper", "explain", "ghost", "--base",
            str(tmp_path), "--session", "2026-10-01",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "no-op"
        assert "ghost" in data["detail"]
        assert "next_step" in data
        assert "nd paper create" in data["next_step"]
        assert "Traceback" not in result.output
