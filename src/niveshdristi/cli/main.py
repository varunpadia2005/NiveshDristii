"""`nd` CLI — Typer-based command line interface."""

from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional
import json

import typer
from rich.console import Console
from rich.table import Table

from niveshdristi.config import (
    load_config,
    load_mandate,
    load_universe,
    load_strategy,
    get_config,
)
from niveshdristi.core.errors import ConfigurationError

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
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    ctx.obj["config_file"] = config_file


def _output(data: dict, json_output: bool) -> None:
    if json_output:
        console.print(json.dumps(data, default=str, indent=2))
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


# Apply common options to all commands
@app.callback()
def main_callback(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
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
    cfg = load_config(ctx.obj.get("config_file"))
    if show:
        _output(cfg.model_dump(), ctx.obj["json_output"])
    if validate:
        console.print("[green]✓[/green] Config valid")


# ============================================================
# Data commands
# ============================================================

data_app = typer.Typer(help="Data management commands")
app.add_typer(data_app, name="data")


@data_app.command("fetch")
def data_fetch(
    ctx: typer.Context,
    tickers: list[str] = typer.Argument(..., help="Tickers to fetch"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
):
    """Fetch price data for tickers."""
    console.print(f"[yellow]Not implemented yet[/yellow]: fetch {tickers} from {provider}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@data_app.command("refresh")
def data_refresh(
    ctx: typer.Context,
    universe: str = typer.Option("nifty50", "--universe", "-u", help="Universe name"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
):
    """Refresh all data for a universe."""
    console.print(f"[yellow]Not implemented yet[/yellow]: refresh {universe} from {provider}")
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
    as_of: Optional[str] = typer.Option(None, "--as-of", help="As-of date (YYYY-MM-DD)"),
):
    """Generate signals for a ticker."""
    console.print(f"[yellow]Not implemented yet[/yellow]: generate signal for {ticker}")
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
    start: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
):
    """Run backtest."""
    console.print(f"[yellow]Not implemented yet[/yellow]: backtest {mandate}/{universe}/{strategy}")
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
    console.print(f"[yellow]Not implemented yet[/yellow]: create paper fund {name}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("tick")
def paper_tick(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    as_of: Optional[str] = typer.Option(None, "--as-of", help="As-of date (YYYY-MM-DD)"),
):
    """Execute one paper trading tick."""
    console.print(f"[yellow]Not implemented yet[/yellow]: tick fund {fund_id}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("status")
def paper_status(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Show paper fund status."""
    console.print(f"[yellow]Not implemented yet[/yellow]: status for fund {fund_id}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("halt")
def paper_halt(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Halt paper fund (kill switch)."""
    console.print(f"[yellow]Not implemented yet[/yellow]: halt fund {fund_id}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


@paper_app.command("resume")
def paper_resume(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
):
    """Resume halted paper fund."""
    console.print(f"[yellow]Not implemented yet[/yellow]: resume fund {fund_id}")
    _output({"status": "not_implemented"}, ctx.obj["json_output"])


# ============================================================
# Validation commands
# ============================================================

@app.command()
def validate(
    ctx: typer.Context,
    market_literals: bool = typer.Option(True, "--market-literals/--no-market-literals", help="Check for market-specific literals in core/engine"),
):
    """Run validation checks."""
    results = {"checks": []}

    if market_literals:
        from niveshdristi.validation.market_literals import scan_market_literals
        issues = scan_market_literals()
        results["checks"].append({
            "name": "market_literals_in_core_engine",
            "passed": len(issues) == 0,
            "issues": issues,
        })

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


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    app()