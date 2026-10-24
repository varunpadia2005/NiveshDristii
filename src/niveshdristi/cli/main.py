"""`nd` CLI — Typer-based command line interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from niveshdristi.config import (
    load_config,
)
from niveshdristi.config_loader import (
    load_layered_config,
    load_mandate,
    load_strategy,
    load_universe,
)

app = typer.Typer(
    name="nd",
    help="NiveshDristi — AI-assisted portfolio research for Indian equities",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


# ============================================================
# Global options
# ============================================================

def _common_options(
    ctx: typer.Context,
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    ctx.obj["config_file"] = config_file


def _output(data: dict, json_output: bool) -> None:
    if json_output:
        # Plain print, not console.print: Rich wraps at the terminal width and
        # can insert newlines inside JSON string literals, producing invalid
        # JSON on narrow terminals. stdout must be pure, width-independent JSON.
        print(json.dumps(data, default=str, indent=2))
    else:
        # Pretty print as table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Key")
        table.add_column("Value")
        for k, v in data.items():
            if isinstance(v, dict):
                v = json.dumps(v, default=str, indent=2)
            table.add_row(str(k), str(v))
        console.print(table)


def _diagnostic(message: str, json_output: bool) -> None:
    """Human-facing diagnostics; must never pollute stdout in --json mode."""
    if json_output:
        print(message, file=sys.stderr)
    else:
        console.print(message)


# Apply common options to all commands
@app.callback()
def main_callback(
    ctx: typer.Context,
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    _common_options(ctx, config_file, json_output)


# ============================================================
# Config commands
# ============================================================

@app.command()
def config(
    ctx: typer.Context,
    show: bool = typer.Option(False, "--show", help="Show current config"),
    validate: bool = typer.Option(False, "--validate", help="Validate config"),
):
    """Manage configuration."""
    config_file = ctx.obj.get("config_file")
    raw = load_layered_config(user_config_path=config_file)
    from niveshdristi.config import Settings
    cfg = Settings(**raw)
    if show:
        _output(cfg.model_dump(), ctx.obj["json_output"])
    if validate:
        _output({"valid": True, "message": "Config schema valid"}, ctx.obj["json_output"])


# ============================================================
# Data commands
# ============================================================

data_app = typer.Typer(help="Data management commands")
app.add_typer(data_app, name="data")


@data_app.command("fetch")
def data_fetch(
    ctx: typer.Context,
    tickers: list[str] = typer.Argument(..., help="Tickers to fetch"),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
):
    """Fetch price data for tickers."""
    _diagnostic(f"Not implemented yet: fetch {tickers} from {provider}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@data_app.command("refresh")
def data_refresh(
    ctx: typer.Context,
    universe: str = typer.Option("nifty50", "--universe", "-u", help="Universe name"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
):
    """Refresh all data for a universe."""
    _diagnostic(f"Not implemented yet: refresh {universe} from {provider}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


# ============================================================
# Signals commands
# ============================================================

signals_app = typer.Typer(help="Signal generation commands")
app.add_typer(signals_app, name="signals")


@signals_app.command("generate")
def signals_generate(
    ctx: typer.Context,
    ticker: str = typer.Argument(..., help="Ticker symbol"),
    as_of: str | None = typer.Option(None, "--as-of", help="As-of date (YYYY-MM-DD)"),
):
    """Generate signals for a ticker."""
    _diagnostic(f"Not implemented yet: generate signal for {ticker}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


# ============================================================
# Backtest commands
# ============================================================

backtest_app = typer.Typer(help="Backtesting commands")
app.add_typer(backtest_app, name="backtest")


@backtest_app.command("run")
def backtest_run(
    ctx: typer.Context,
    mandate: str = typer.Option("core", "--mandate", "-m", help="Mandate name"),
    universe: str = typer.Option("nifty50", "--universe", "-u", help="Universe name"),
    strategy: str = typer.Option("signal_based", "--strategy", "-s", help="Strategy name"),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
):
    """Run backtest."""
    _diagnostic(
        f"Not implemented yet: backtest {mandate}/{universe}/{strategy}", ctx.obj["json_output"]
    )
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


# ============================================================
# Paper trading commands
# ============================================================

paper_app = typer.Typer(help="Paper trading commands")
app.add_typer(paper_app, name="paper")


@paper_app.command("create")
def paper_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Fund name"),
    mandate: str = typer.Option("core", "--mandate", "-m", help="Mandate name"),
    capital: float = typer.Option(1_000_000, "--capital", help="Initial capital"),
):
    """Create a new paper fund."""
    _diagnostic(f"Not implemented yet: create paper fund {name}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("tick")
def paper_tick(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    as_of: str | None = typer.Option(None, "--as-of", help="As-of date (YYYY-MM-DD)"),
):
    """Execute one paper trading tick."""
    _diagnostic(f"Not implemented yet: tick fund {fund_id}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("status")
def paper_status(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Show paper fund status."""
    _diagnostic(f"Not implemented yet: status for fund {fund_id}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("halt")
def paper_halt(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Halt paper fund (kill switch)."""
    _diagnostic(f"Not implemented yet: halt fund {fund_id}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("resume")
def paper_resume(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Resume halted paper fund."""
    _diagnostic(f"Not implemented yet: resume fund {fund_id}", ctx.obj["json_output"])
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


# ============================================================
# Validation commands
# ============================================================

@app.command()
def validate(ctx: typer.Context):
    """Run validation checks."""
    import warnings

    import yaml

    from niveshdristi.config import Settings
    from niveshdristi.markets import IN_NSE_PROFILE

    results: dict[str, Any] = {"checks": []}

    # Check 0: Config file has no unknown keys
    config_file = ctx.obj.get("config_file")
    if config_file:
        config_path = Path(config_file)
    else:
        config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # Get known top-level keys from Settings model
        known_keys = set(Settings.model_fields.keys())
        unknown = set(raw.keys()) - known_keys
        if unknown:
            results["checks"].append({
                "name": "config_unknown_keys",
                "passed": False,
                "error": f"Unknown config keys: {sorted(unknown)}",
            })
        else:
            results["checks"].append({
                "name": "config_unknown_keys",
                "passed": True,
                "message": "No unknown keys in config file",
            })
    else:
        results["checks"].append({
            "name": "config_unknown_keys",
            "passed": True,
            "message": "No config file found, skipping unknown key check",
        })

    # Check 1: IN_NSE profile loads and is valid
    try:
        profile = IN_NSE_PROFILE
        assert profile.market_id == "IN_NSE"
        assert profile.shorting_allowed is False
        assert profile.settlement.days == 1
        results["checks"].append({
            "name": "in_nse_profile",
            "passed": True,
            "message": "IN_NSE profile loads and has expected values",
        })
    except Exception as e:
        results["checks"].append({
            "name": "in_nse_profile",
            "passed": False,
            "error": str(e),
        })

    # Check 2: Example mandate
    try:
        mandate = load_mandate("core", mandates_dir=Path("mandates"))
        assert mandate.name == "core"
        assert mandate.market_id == "IN_NSE"
        results["checks"].append({
            "name": "mandate_core",
            "passed": True,
            "message": "Core mandate loads and validates",
        })
    except Exception as e:
        results["checks"].append({
            "name": "mandate_core",
            "passed": False,
            "error": str(e),
        })

    # Check 3: Example universes
    for name in ["nifty10", "nifty50", "nifty100"]:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                universe = load_universe(name, universes_dir=Path("universes"))
                assert universe.name == name
                assert len(universe.tickers) > 0
                msg = f"Universe {name} loads with {len(universe.tickers)} tickers"
                warns = []
                if w:
                    for warning in w:
                        warns.append(str(warning.message))
                results["checks"].append({
                    "name": f"universe_{name}",
                    "passed": True,
                    "message": msg,
                    "warnings": warns if warns else None,
                })
            except Exception as e:
                results["checks"].append({
                    "name": f"universe_{name}",
                    "passed": False,
                    "error": str(e),
                })

    # Check 4: Example strategy
    try:
        strategy = load_strategy("signal_based", strategies_dir=Path("strategies"))
        assert strategy.name == "signal_based"
        assert len(strategy.models) > 0
        results["checks"].append({
            "name": "strategy_signal_based",
            "passed": True,
            "message": f"Strategy signal_based loads with {len(strategy.models)} models",
        })
    except Exception as e:
        results["checks"].append({
            "name": "strategy_signal_based",
            "passed": False,
            "error": str(e),
        })

    # Check 5: Config schema validation
    try:
        load_config()
        results["checks"].append({
            "name": "config_schema",
            "passed": True,
            "message": "Config schema validates with defaults",
        })
    except Exception as e:
        results["checks"].append({
            "name": "config_schema",
            "passed": False,
            "error": str(e),
        })

    results["summary"] = {
        "total": len(results["checks"]),
        "passed": sum(1 for c in results["checks"] if c.get("passed")),
        "failed": sum(1 for c in results["checks"] if not c.get("passed")),
    }

    _output(results, ctx.obj["json_output"])

    # Exit with error code if any check failed
    if any(not c["passed"] for c in results["checks"]):
        raise typer.Exit(code=1)


# ============================================================
# Version / info
# ============================================================

@app.command()
def version(ctx: typer.Context):
    """Show version."""
    from niveshdristi import __version__
    _output({"version": __version__}, ctx.obj["json_output"])


@app.command("models")
def models(ctx: typer.Context):
    """List registered alpha models (id, horizon, data, pit_safe, status).

    COMPOSITION POINT: this command builds the registry via
    alpha.registry.default_registry(), which registers the neutral
    alpha/quant models and then delegates to market packs
    (markets/in_nse/models.register_all).
    """
    # COMPOSITION POINT (lazy): the CLI wires the neutral alpha/quant models
    # and the market packs together. alpha/ itself never imports markets/.
    from niveshdristi.alpha.quant.earnings_drift import EarningsDrift
    from niveshdristi.alpha.quant.fundamental_guardrails import FundamentalGuardrails
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.quality_value import QualityValue
    from niveshdristi.alpha.quant.regime import RegimeModel
    from niveshdristi.alpha.quant.sector_rotation import SectorRotation
    from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
    from niveshdristi.alpha.registry import ModelRegistry
    from niveshdristi.markets.in_nse.models import register_all as register_in_nse

    reg = ModelRegistry()
    reg.register_all(
        [
            TaEnsemble().registry_entry(),
            PriceRangeModel().registry_entry(),
            TimeSeriesMomentum().registry_entry(),
            CrossSectionalMomentum().registry_entry(),
            MeanReversion().registry_entry(),
            LowVolatility().registry_entry(),
            RegimeModel().registry_entry(),
            FundamentalGuardrails().registry_entry(),
            QualityValue().registry_entry(),
            EarningsDrift().registry_entry(),
            SectorRotation().registry_entry(),
        ]
    )
    register_in_nse(reg)
    entries = [
        {
            "model_id": e.model_id,
            "horizon_days": e.horizon_days,
            "required_data": list(e.required_data),
            "pit_safe": e.pit_safe,
            "data_status": e.data_status,
        }
        for e in reg.entries()
    ]
    _output(
        {"count": len(entries), "models": entries},
        ctx.obj["json_output"],
    )


@app.command("models-list")
def models_list(ctx: typer.Context):
    """Typer turns 'models list' into a subcommand; flat alias for humans."""
    models(ctx)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    app()
