"""FX-O (fix run 5): the US costs_not_modeled limitation code propagates
through the run_backtest RESULT and the CLI backtest output.

The engine's run_backtest already accepts extra_limitations (caller may
ADD codes) — no core/engine edit is needed: services/backtest_lab passes
the fund header's costs_not_modeled code (recorded at creation by
us_market_rules' marker) into the engine, and the CLI surfaces the
result's limitation codes plus the fund's banner. A US fund's backtest
must NEVER present itself without the costs-not-modeled disclosure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from niveshdristi.cli.main import app

REPO = Path(__file__).resolve().parent.parent
runner = CliRunner()


def _build_demo(base: Path, fund_id: str, market: str) -> None:
    proc = subprocess.run(
        [sys.executable, "tools/make_demo_fund.py", "--base", str(base),
         "--fund-id", fund_id, "--market", market],
        capture_output=True, text=True, cwd=REPO, timeout=900,
    )
    assert proc.returncode == 0, proc.stderr[-400:]


class TestCostsNotModeledPropagation:
    def test_us_demo_backtest_carries_costs_not_modeled(self, tmp_path):
        """SPEC (fix run 5, headline 3): a US_NYSE fund's backtest result
        carries costs_not_modeled in its limitation codes and the COSTS
        NOT MODELED banner in the CLI output."""
        _build_demo(tmp_path, "demo_us", "US_NYSE")
        r = runner.invoke(
            app, ["--json", "backtest", "run", "demo_us",
                  "--base", str(tmp_path)]
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok", data
        assert "costs_not_modeled" in data["limitation_codes"], data
        assert data["banner"] is not None
        assert "COSTS NOT MODELED" in data["banner"]

    def test_in_demo_backtest_has_no_costs_flag(self, tmp_path):
        """The IN_NSE fund's backtest must NOT claim costs_not_modeled
        (its rates are real, merely unverified)."""
        _build_demo(tmp_path, "demo_in", "IN_NSE")
        r = runner.invoke(
            app, ["--json", "backtest", "run", "demo_in",
                  "--base", str(tmp_path)]
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["status"] == "ok", data
        assert "costs_not_modeled" not in data["limitation_codes"], data
        assert "COSTS NOT MODELED" not in (data.get("banner") or "")
