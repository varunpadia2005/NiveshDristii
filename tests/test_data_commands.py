"""P12-A: the data/signals CLI commands (previously interface-stability
stubs) implemented through the market DataClient seams.

Offline: the IN_NSE yfinance adapter's _fetch is monkeypatched (same
pattern as test_fetch_window); the US_NYSE shell needs no network (it
raises a typed DataError by design).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import pytest
from typer.testing import CliRunner

from niveshdristi.cli.main import app

runner = CliRunner()


def _fake_yf_frame(days: int, end: date) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=days, freq="D")
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [1_000_000] * n,
        },
        index=idx,
    )


@pytest.fixture
def fake_in_nse(monkeypatch):
    """Patch the IN_NSE adapter's low-level fetch (no network)."""
    calls: list[tuple[str, str, str]] = []

    class _FakeFetch:
        def _fetch(self, provider_symbol, start, end, auto_adjust):
            calls.append((provider_symbol, str(start), str(end)))
            return _fake_yf_frame(30, end)

    monkeypatch.setattr(
        "niveshdristi.markets.in_nse.providers.yfinance_adapter.YFinanceClient._fetch",
        _FakeFetch._fetch,
    )
    return calls


END = date.today() - timedelta(days=3)
START = END - timedelta(days=30)


class TestDataFetch:
    def test_fetch_reports_rows_per_symbol(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE", "TCS",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok"
        assert data["provider"] == "yfinance"
        assert data["market"] == "IN_NSE"
        syms = {s["symbol"]: s for s in data["symbols"]}
        assert set(syms) == {"RELIANCE", "TCS"}
        for s in syms.values():
            assert s["rows"] > 0
            assert s["first"] <= s["last"]

    def test_fetch_passes_bounded_window_to_the_adapter(
        self, fake_in_nse, tmp_path
    ):
        runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert fake_in_nse, "the adapter must have been called"
        for _sym, s, e in fake_in_nse:
            assert date.fromisoformat(s) == START
            assert date.fromisoformat(e) == END

    def test_fetch_us_market_typed_refusal(self, tmp_path):
        """US_NYSE: the shell provider raises a typed DataError — never a
        silent empty result."""
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "AAPL",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--market", "US_NYSE"],
        )
        assert r.exit_code == 1, r.output
        data = json.loads(r.output)
        assert data["status"] == "error"
        assert "US_NYSE" in data["error"]

    def test_fetch_unknown_market_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--market", "NOPE"],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"
        assert "NOPE" in data["error"]

    def test_fetch_missing_dates_usage_error(self, tmp_path):
        r = runner.invoke(app, ["--json", "data", "fetch", "RELIANCE"])
        assert r.exit_code == 2

    def test_fetch_unknown_provider_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "fetch", "RELIANCE",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--provider", "madeup"],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"


class TestDataRefresh:
    def test_refresh_nifty50_reports_all_tickers(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nifty10",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok"
        assert data["universe"] == "nifty10"
        assert len(data["symbols"]) == 10
        assert all(s["rows"] > 0 for s in data["symbols"])

    def test_refresh_unknown_universe_typed_error(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nope50",
             "--start", START.isoformat(), "--end", END.isoformat()],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"

    def test_refresh_reports_force_flag(self, fake_in_nse, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "data", "refresh", "--universe", "nifty10",
             "--start", START.isoformat(), "--end", END.isoformat(),
             "--force"],
        )
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["force"] is True


class TestSignalsGenerate:
    def test_generate_reports_models_and_blend(self, fake_in_nse, tmp_path):
        as_of = END.isoformat()
        r = runner.invoke(
            app,
            ["--json", "signals", "generate", "RELIANCE", "--as-of", as_of],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok"
        assert data["ticker"] == "RELIANCE"
        assert data["as_of"] == as_of
        assert isinstance(data["signals"], list)
        assert isinstance(data["blended"], dict)
        assert all(-1.0 <= v <= 1.0 for v in data["blended"].values())

    def test_generate_us_market_typed_refusal(self, tmp_path):
        r = runner.invoke(
            app,
            ["--json", "signals", "generate", "AAPL",
             "--as-of", END.isoformat(), "--market", "US_NYSE"],
        )
        assert r.exit_code == 1
        data = json.loads(r.output)
        assert data["status"] == "error"
        assert "US_NYSE" in data["error"]

    def test_generate_missing_as_of_defaults_to_today(
        self, fake_in_nse, tmp_path
    ):
        r = runner.invoke(app, ["--json", "signals", "generate", "RELIANCE"])
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["as_of"] == date.today().isoformat()

def _command_tree(plain: str) -> str:
    """P16-A-3: the semantic command tree = everything from the first
    "Commands config" occurrence (the tree start) onward."""
    i = plain.find("Commands config")
    assert i != -1, (
        "command-tree marker 'Commands config' not found in normalized "
        f"help output: {plain[:200]!r}"
    )
    return plain[i:]


def _plain_cli_text(text: str) -> str:
    """P13-B: normalize rich/typer help output for cross-platform checks.

    Strips ANSI escapes, rich table furniture (borders/padding), and
    collapses whitespace — robust against FORCE_COLOR, COLUMNS/terminal
    width, and wrap-point differences between Windows and ubuntu."""
    import re

    t = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    t = re.sub(r"[│╭╮╯╰┌┐└┘─═]+", " ", t)
    return " ".join(t.split())


class TestHelpTextDogfood:
    """P13-A #5/#6: the help text says what the flags actually do."""

    def test_force_flag_documents_no_cache(self):
        from typer.testing import CliRunner

        r = CliRunner().invoke(app, ["--json", "data", "fetch", "--help"])
        assert r.exit_code == 0
        plain = _plain_cli_text(r.output)
        assert "nothing is cached" in plain, (
            "--force help must state that nothing is cached (P13-A #5)"
        )
        assert "--end" in plain, "--end help must be present (P13-A #6)"
        assert "exclusive" in plain, (
            "--end help must state exclusivity (P13-A #6)"
        )


class TestPythonMDunderMain:
    """P13-A #7: `python -m niveshdristi` must run the same CLI."""

    def test_module_help_matches_cli_help(self, tmp_path):
        import subprocess
        import sys

        base = [sys.executable, "-m", "niveshdristi"]
        r1 = subprocess.run(base + ["--help"], capture_output=True, text=True,
                            timeout=120)
        assert r1.returncode == 0, r1.stderr
        r2 = subprocess.run(
            [sys.executable, "-c",
             "from niveshdristi.cli.main import app; app()",
             "--help"],
            capture_output=True, text=True, timeout=120,
        )
        assert r2.returncode == 0, r2.stderr
        # P13-B: compare SEMANTIC content only. The usage line embeds the
        # prog name ('python -m niveshdristi' vs '-c') and rich pads every
        # line to the box width (both differ across invocations/OSes).
        # P16-A-3: do NOT key on "Usage:" / "COMMAND [ARGS]" — rich wraps
        # both at narrow widths (COLUMNS=40 mutates the ellipsis and the
        # colon), which broke the P13-B split. Instead compare from the
        # command-tree marker onward: after whitespace collapse, both
        # invocations render "... exit. Commands config Manage
        # configuration. ..." identically, so everything from the first
        # "Commands config" occurrence is the semantic command tree.
        p1 = _plain_cli_text(r1.stdout)
        p2 = _plain_cli_text(r2.stdout)
        tree1 = _command_tree(p1)
        tree2 = _command_tree(p2)
        assert tree1 == tree2, (
            "the two invocations must render the identical command tree "
            f"(modulo the prog name); got:\n{tree1[:200]}\nvs\n{tree2[:200]}"
        )
        assert len(tree1) > 100, (
            "non-vacuity: the command tree must be non-trivial"
        )
        assert "NiveshDristi" in p1


class TestTickHaltHint:
    """P13-A #8: the tick failure JSON carries the resume hint."""

    def test_halt_payload_includes_resume_hint(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        import niveshdristi.markets.in_nse.providers.yfinance_adapter as yfa
        from niveshdristi.cli.main import app

        def bad_fetch(provider_symbol, start, end, auto_adjust):
            # Frame FETCHES fine but is malformed for advance() (no
            # "close" column) -> the tick loop raises -> amendment F halt.
            import pandas as pd

            idx = pd.date_range(start, end, freq="D")
            return pd.DataFrame(
                {"Open": [100.0] * len(idx), "High": [101.0] * len(idx),
                 "Low": [99.0] * len(idx), "Volume": [1_000_000] * len(idx)},
                index=pd.DatetimeIndex(idx, name="Date"),
            )

        monkeypatch.setattr(
            yfa.YFinanceClient, "_fetch", staticmethod(bad_fetch)
        )
        runner = CliRunner()
        T = str(tmp_path)
        runner.invoke(app, ["--json", "paper", "create", "hint_fund",
                            "--created", "2026-09-24",
                            "--universe", "SYN090,SYN091", "--base", T])
        r = runner.invoke(app, ["--json", "paper", "tick", "hint_fund",
                                "--as-of", "2026-10-02", "--base", T])
        assert r.exit_code == 1
        import json as _j
        d = _j.loads(r.output)
        assert d["halted"] is True
        assert "nd paper resume --note" in d["next_step"]
