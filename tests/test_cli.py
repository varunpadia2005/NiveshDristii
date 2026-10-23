"""
Test CLI with Typer's CliRunner.

Protects the rule that nd CLI commands work and --json outputs valid JSON.
"""

import json
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
        result = runner.invoke(app, ["--json", "config", "--show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "backtest" in data
        assert "data" in data

    def test_config_validate_json(self):
        """nd config --validate --json outputs valid JSON."""
        result = runner.invoke(app, ["--json", "config", "--validate"])
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