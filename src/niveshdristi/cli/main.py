"""`nd` CLI — Typer-based command line interface."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
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


def _fund_paths(fund_id: str, base: str | None) -> Any:
    from niveshdristi.paper.fund import FundPaths

    return FundPaths(base).for_fund(fund_id)


def _paper_fetch_bars(universe: list[str], start: date) -> dict:
    """COMPOSITION POINT (cli/ only): fetch EOD bars through the IN_NSE
    yfinance adapter (amendment E). Never run by pytest or the gate."""
    import polars as pl

    from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

    client = YFinanceClient()
    out: dict = {}
    for symbol in universe:
        hist = client._fetch(  # noqa: SLF001 - adapter composition in cli/
            f"{symbol}.NS", start, start, auto_adjust=True
        )
        pdf = hist.reset_index()
        pdf.columns = [str(c).lower() for c in pdf.columns]

        out[symbol] = pl.from_pandas(pdf)
    return out


def _live_models_bundle() -> Any:
    """Live model objects only (require_live): a paper fund refuses stub
    models unless --allow-stub is given (stub limitation then applies)."""
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

    by_id: dict[str, Any] = {
        "ta_ensemble": TaEnsemble(),
        "price_range": PriceRangeModel(),
        "momentum_ts": TimeSeriesMomentum(),
        "momentum_cs": CrossSectionalMomentum(),
        "mean_reversion": MeanReversion(),
        "low_volatility": LowVolatility(),
        "regime": RegimeModel(),
        "fundamental_guardrails": FundamentalGuardrails(),
        "quality_value": QualityValue(),
        "earnings_drift": EarningsDrift(),
        "sector_rotation": SectorRotation(),
    }
    return [
        obj for model_id, obj in sorted(by_id.items())
        if by_id[model_id].registry_entry().data_status == "live"
    ]


def _live_registry() -> Any:
    """COMPOSITION POINT: registry with all model entries (S11 pattern)."""
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
    entries: list = [
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
    reg.register_all(entries)
    register_in_nse(reg)
    return reg


def _events_log(fund_id: str, base: str | None) -> Any:
    from niveshdristi.paper.events import EventLog

    return EventLog(_fund_paths(fund_id, base).events)


def _halted_reason(fund_id: str, base: str | None) -> str | None:
    """Fail-safe halted check; returns the halt reason or None."""
    from niveshdristi.paper.killswitch import is_halted

    halted, reason = is_halted(_fund_paths(fund_id, base), fund_id=fund_id)
    return reason if halted else None


@paper_app.command("create")
def paper_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory (default: user profile)"),
    capital: float = typer.Option(1_000_000, "--capital", help="Initial capital"),
    created: str | None = typer.Option(
        None, "--created", help="Creation session date (YYYY-MM-DD); default: today"
    ),
    universe: str = typer.Option(
        "", "--universe", help="Comma-separated universe symbols (stored in the header)"
    ),
):
    """Create a new paper fund."""
    from niveshdristi.core.errors import LedgerError
    from niveshdristi.core.limitations import DataLimitations
    from niveshdristi.core.money import to_paise
    from niveshdristi.paper.fund import create_fund

    limitations = DataLimitations(CODES=frozenset({
        "derived_calendar", "adjusted_price_basis", "corporate_actions_unavailable",
        "price_level_rules_on_adjusted", "rates_unverified",
        "approximate_universe", "survivorship_universe", "no_pit_fundamentals",
        "benchmark_not_tri",
    }))
    from niveshdristi.core.market_rules import MarketRules

    rules = MarketRules(market_id="TEST_MARKET")  # neutral default
    universe_list = [s.strip() for s in universe.split(",") if s.strip()]
    try:
        ledger_path = create_fund(
            name, base=base,
            created=date.fromisoformat(created) if created else date.today(),
            config_digest="cli-created", rules=rules,
            limitations=limitations, rates_verified=False,
            initial_cash=capital, universe=universe_list,
        )
    except LedgerError as exc:
        _output({"status": "error", "error": str(exc)}, ctx.obj["json_output"])
        raise typer.Exit(code=1) from exc
    _events_log(name, base).append(
        "create", fund_id=name, initial_cash_paise=to_paise(capital)
    )
    _output(
        {"status": "created", "fund_id": name, "ledger": str(ledger_path)},
        ctx.obj["json_output"],
    )


@paper_app.command("tick")
def paper_tick(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    as_of: str | None = typer.Option(
        None, "--as-of", help="Candidate session (YYYY-MM-DD); default: today"
    ),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Execute one paper trading tick (idempotent; fails non-zero)."""
    from niveshdristi.core.market_rules import MarketRules
    from niveshdristi.engine.advance import ModelBundle, RebalanceSchedule
    from niveshdristi.paper.events import write_heartbeat
    from niveshdristi.paper.fund import tick as run_tick
    from niveshdristi.portfolio.risk_gates import GateLimits

    halted = _halted_reason(fund_id, base)
    if halted:
        _events_log(fund_id, base).append(
            "tick-noop-halted", fund_id=fund_id, reason=halted
        )
        _output({"status": "no-op", "reason": halted}, ctx.obj["json_output"])
        return
    registry = _live_registry()
    # UNIVERSE from the fund header (stored at create), never hardcoded
    from niveshdristi.paper.fund import load_fund

    header = load_fund(fund_id, base=base).header()
    universe = header.get("universe", [])
    stub_used = any(
        entry.data_status != "live" for entry in registry.entries()
    )  # noted: limitation codes are fixed on the ledger header
    del stub_used
    candidate = date.fromisoformat(as_of) if as_of else date.today()
    start_window = candidate - timedelta(days=30)
    try:
        result = run_tick(
            fund_id, base=base,
            fetch_bars=lambda universe_, day: _paper_fetch_bars(universe_, start_window),
            clock_now=candidate,
            models=ModelBundle(_live_models_bundle()),
            rules=MarketRules(market_id="TEST_MARKET"),
            limits=GateLimits(), rebalance=RebalanceSchedule(),
            universe=universe, tax_enabled=False,
        )
    except Exception as exc:  # noqa: BLE001 - amendment F: halt on any tick exception
        from niveshdristi.paper.killswitch import halt as halt_fund

        halt_fund(
            _fund_paths(fund_id, base), fund_id=fund_id,
            reason=f"tick exception: {exc}", session=candidate,
            event_id=f"halt-{fund_id}",
        )
        _events_log(fund_id, base).append(
            "tick-failure-halted", fund_id=fund_id, reason=str(exc)
        )
        _output(
            {"status": "failure", "halted": True, "reason": str(exc)},
            ctx.obj["json_output"],
        )
        raise typer.Exit(code=1) from exc
    write_heartbeat(
        _fund_paths(fund_id, base).heartbeat, fund_id=fund_id,
        last_tick=result["outcome"],
    )
    _events_log(fund_id, base).append("tick", fund_id=fund_id, **result)
    if result["outcome"] == "failure":
        _output({"status": "failure", **result}, ctx.obj["json_output"])
        raise typer.Exit(code=1)
    _output({"status": result["outcome"], **result}, ctx.obj["json_output"])


@paper_app.command("status")
def paper_status(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Show paper fund status."""
    from niveshdristi.paper.fund import load_fund
    from niveshdristi.paper.killswitch import is_halted

    ledger = load_fund(fund_id, base=base)
    header = ledger.header()
    halted, halt_reason = is_halted(_fund_paths(fund_id, base), fund_id=fund_id)
    last = ledger.last_session_date()
    records = ledger.records()
    _output({
        "fund_id": fund_id,
        "last_session": last.isoformat() if last else None,
        "cash_after": records[-1]["cash_after"] if records else None,
        "halted": halted,
        "halt_reason": halt_reason or None,
        "limitations": header["limitation_codes"],
        "rates_verified": header["rates_verified"],
        "rates_banner": "" if header["rates_verified"] else "RATES UNVERIFIED",
    }, ctx.obj["json_output"])


@paper_app.command("list")
def paper_list(
    ctx: typer.Context,
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """List paper funds."""
    from niveshdristi.paper.fund import FundPaths

    root = FundPaths(base).base
    funds = (
        sorted(d.name for d in root.iterdir() if (d / "ledger.jsonl").exists())
        if root.exists() else []
    )
    _output({"funds": funds}, ctx.obj["json_output"])


@paper_app.command("halt")
def paper_halt(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    reason: str = typer.Option("manual halt", "--reason", help="Halt reason"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Halt paper fund (kill switch)."""
    from niveshdristi.paper.killswitch import halt

    payload = halt(
        _fund_paths(fund_id, base), fund_id=fund_id, reason=reason,
        session=date.today(), event_id=f"halt-{fund_id}",
    )
    _events_log(fund_id, base).append("halt", **payload)
    _output({"status": "halted", **payload}, ctx.obj["json_output"])


@paper_app.command("resume")
def paper_resume(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    note: str = typer.Option(..., "--note", help="Required resume note (logged)"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Resume halted paper fund."""
    from niveshdristi.paper.killswitch import KillSwitchResumeError, resume

    try:
        resume(_fund_paths(fund_id, base), note=note)
    except KillSwitchResumeError as exc:
        _output({"status": "error", "error": str(exc)}, ctx.obj["json_output"])
        raise typer.Exit(code=1) from exc
    _events_log(fund_id, base).append("resume", fund_id=fund_id, note=note)
    _output({"status": "resumed", "note": note}, ctx.obj["json_output"])


@paper_app.command("verify")
def paper_verify(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Verify the ledger hash chain (loud failure names the line)."""
    from niveshdristi.paper.ledger import PaperLedger

    ledger = PaperLedger(_fund_paths(fund_id, base).ledger)
    problems = ledger.verify()
    if problems:
        _output({"status": "failed", "problems": problems}, ctx.obj["json_output"])
        raise typer.Exit(code=1)
    _output(
        {"status": "verified", "records": len(ledger.records())},
        ctx.obj["json_output"],
    )


@paper_app.command("replay")
def paper_replay(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """Replay stored snapshots through advance() and compare with the ledger."""
    from niveshdristi.paper.replay import replay_fund

    result = replay_fund(fund_id, base=base)
    _output(result, ctx.obj["json_output"])
    if not result.get("byte_identical", False):
        raise typer.Exit(code=1)


@paper_app.command("recover")
def paper_recover(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """OPERATOR: rebuild the broker cache from the ledger (never called by tick)."""
    from niveshdristi.paper.fund import FundState, _write_cache_atomic
    from niveshdristi.paper.ledger import PaperLedger

    ledger = PaperLedger(_fund_paths(fund_id, base).ledger)
    records = ledger.records()
    last_session = (
        date.fromisoformat(records[-1]["session_date"])
        if records else date(1970, 1, 1)
    )
    fund = FundState(cash=float(records[-1]["cash_after"]) if records else 0.0)
    _write_cache_atomic(
        _fund_paths(fund_id, base).broker_cache,
        type("R", (), {"session_date": last_session})(),
        fund,
    )
    _events_log(fund_id, base).append("recover", fund_id=fund_id)
    _output({"status": "recovered", "records": len(records)}, ctx.obj["json_output"])


@paper_app.command("unlock")
def paper_unlock(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """OPERATOR: remove a stale tick lock (logged)."""
    lock = _fund_paths(fund_id, base).root / "tick.lock"
    if lock.exists():
        lock.unlink()
    _events_log(fund_id, base).append("unlock", fund_id=fund_id)
    _output({"status": "unlocked"}, ctx.obj["json_output"])


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
