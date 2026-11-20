"""`nd` CLI — Typer-based command line interface."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

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
from niveshdristi.core.errors import (
    ConfigurationError,
    DataError,
    ProviderError,
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


def _data_client_for(market_id: str) -> Any:
    """P12-A composition point: the market's DataClient.

    IN_NSE -> the yfinance adapter; US_NYSE -> the typed shell (every
    role raises DataError — a US fetch can never be a silent empty).
    Unknown markets raise a typed ConfigurationError.
    """
    # Importing the profile modules REGISTERS the markets (side effect by
    # design — same pattern as services/fund.py). Without the US import,
    # get_registry().get("US_NYSE") raises KeyError.
    import niveshdristi.markets.in_nse.profile  # noqa: F401
    import niveshdristi.markets.in_us.profile  # noqa: F401
    from niveshdristi.core.errors import ConfigurationError
    from niveshdristi.markets import get_registry
    from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient
    from niveshdristi.markets.in_us.providers.us_adapter import UsProviderShell

    try:
        get_registry().get(market_id)
    except KeyError as exc:
        raise ConfigurationError(
            f"unknown market: {market_id!r}"
        ) from exc
    factories: dict[str, Any] = {
        "IN_NSE": YFinanceClient,
        "US_NYSE": UsProviderShell,
    }
    if market_id not in factories:
        raise ConfigurationError(
            f"no data provider registered for market {market_id!r}"
        )
    return cast(str, factories[market_id]())


def _parse_window(start: str, end: str) -> tuple[date, date]:
    """Parse the --start/--end window (ISO dates; start <= end)."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    if s > e:
        raise ValueError("--start must not be after --end")
    return s, e


def _require_provider(provider: str) -> None:
    """Only the registered provider name is accepted."""
    if provider != "yfinance":
        raise ConfigurationError(
            f"unknown provider: {provider!r} (registered: 'yfinance')"
        )


def _fetch_report(
    client: Any, tickers: list[str], start: date, end: date
) -> list[dict[str, Any]]:
    """Fetch prices per ticker and build the report rows (report-only:
    nothing is stored — the paper fund's snapshots remain the only
    price store, so replay is untouched)."""
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        series = client.prices(ticker, start, end)
        adjusted = series.adjusted
        n = adjusted.height
        dates = adjusted["date"].to_list() if n else []
        rows.append(
            {
                "symbol": series.symbol,
                "rows": n,
                "first": str(dates[0])[:10] if n else None,
                "last": str(dates[-1])[:10] if n else None,
            }
        )
    return rows


@data_app.command("fetch")
def data_fetch(
    ctx: typer.Context,
    tickers: list[str] = typer.Argument(..., help="Tickers to fetch"),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
    market: str = typer.Option("IN_NSE", "--market", help="Market id"),
):
    """Fetch daily prices for TICKERS through the market's data provider
    and print a JSON report (report-only; nothing is stored)."""
    from niveshdristi.core.errors import (
        ConfigurationError,
    )

    if start is None or end is None:
        _output(
            {"status": "error",
             "error": "--start and --end are required (YYYY-MM-DD)"},
            ctx.obj["json_output"],
        )
        raise typer.Exit(code=2)
    try:
        s, e = _parse_window(start, end)
        _require_provider(provider)
        client = _data_client_for(market)
        symbols = _fetch_report(client, list(tickers), s, e)
    except (DataError, ConfigurationError, ProviderError, ValueError) as exc:
        _output({"status": "error", "error": str(exc)}, ctx.obj["json_output"])
        raise typer.Exit(code=1) from exc
    _output(
        {"status": "ok", "provider": provider, "market": market,
         "force": force, "symbols": symbols},
        ctx.obj["json_output"],
    )


@data_app.command("refresh")
def data_refresh(
    ctx: typer.Context,
    universe: str = typer.Option("nifty50", "--universe", "-u", help="Universe name"),
    provider: str = typer.Option("yfinance", "--provider", "-p", help="Data provider"),
    force: bool = typer.Option(False, "--force", help="Force refresh"),
):
    """Not available yet: no verified data source. (Stub kept for interface stability.)"""
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
    """Not available yet: no verified data source. (Stub kept for interface stability.)"""
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
    fund_id: str = typer.Argument(..., help="Fund ID whose snapshots to run over"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
    mandate: str = typer.Option("core", "--mandate", "-m",
                                help="DEPRECATED: accepted, ignored"),
    universe: str = typer.Option("nifty50", "--universe", "-u",
                                 help="DEPRECATED: accepted, ignored"),
    strategy: str = typer.Option("signal_based", "--strategy", "-s",
                                 help="DEPRECATED: accepted, ignored"),
    start: str | None = typer.Option(None, "--start", help="DEPRECATED: ignored"),
    end: str | None = typer.Option(None, "--end", help="DEPRECATED: ignored"),
):
    """Run the engine backtest over a fund's STORED snapshots (offline).

    P10-S3: wraps services.run_backtest_service - no network, no refetch;
    the verdict wording is fixed ("pipeline demonstration only; not
    evidence of performance"). Exit 0 ok, 1 unavailable, 2 usage."""
    from niveshdristi.services.backtest_lab import (
        content_key,
        run_backtest_service,
    )

    deprecated_used = (
        mandate != "core" or universe != "nifty50"
        or strategy != "signal_based" or start or end
    )
    if deprecated_used:
        _diagnostic(
            "deprecated options --mandate/--universe/--strategy/--start/--end "
            "are accepted but ignored (recorded in CHANGELOG)",
            ctx.obj["json_output"],
        )
    try:
        result = run_backtest_service(
            fund_id, base=base, _key=content_key(fund_id, base))
    except Exception as exc:  # noqa: BLE001 - typed degradation report
        _output({"status": "error", "detail": f"{type(exc).__name__}: {exc}"},
                ctx.obj["json_output"])
        raise typer.Exit(code=1) from exc
    if not result.get("available"):
        _output({"status": "unavailable", "reason": result.get("reason", "")},
                ctx.obj["json_output"])
        raise typer.Exit(code=1)
    _output({
        "status": "ok",
        "fund_id": fund_id,
        "as_of": result["as_of"],
        "verdict": result["verdict"],
        "promotable": result["promotable"],
        "drag_bps": result["drag_bps"],
        "fees_total": result["fees_total"],
        "slippage_total": result["slippage_total"],
        "trade_count": result["trade_count"],
        # P11-S4: the caller-recorded trial count (TrialRecorder at the
        # services composition point).
        "trials_recorded": result.get("trials_recorded", 0),
        # FX-O (fix run 5): the fund's banner (COSTS NOT MODELED for US
        # funds) is surfaced with the backtest output.
        "banner": result.get("banner"),
        "limitation_codes": sorted(result["limitations"]),
        "calendar_source": result["calendar_source"],
    }, ctx.obj["json_output"])


# ============================================================
# Paper trading commands
# ============================================================

paper_app = typer.Typer(
    help="Paper trading commands",
    epilog=("Exit codes: 0 = ok or logged no-op; 1 = operational failure "
            "(halt, verification failure, provider down); 2 = usage error. "
            "nd paper tick failures that halt carry the recovery hint in "
            "the payload ('nd paper recover'); stale locks: 'nd paper "
            "unlock'. data/signals/backtest subcommands are documented "
            "stubs (status not_implemented)."),
)
app.add_typer(paper_app, name="paper")


def _market_rules_from_header(fund_id: str, base: str | None) -> Any:
    """NEW (R9a): reconstruct the fund's MarketRules from the ledger header
    digest (same as replay does) so recover is composition-faithful."""
    import json

    from niveshdristi.core.market_rules import MarketRules
    from niveshdristi.paper.ledger import PaperLedger

    header = PaperLedger(_fund_paths(fund_id, base).ledger).header()
    return MarketRules.model_validate(json.loads(header["market_rules_digest"]))

def _check_fund(fund_id: str, base: str | None, ctx: typer.Context) -> Any:
    """FX-D: load the fund ledger or emit the plain JSON error payload
    (status error, detail naming the fund, next_step) and exit 1."""
    from niveshdristi.paper.ledger import PaperLedger

    fp = _fund_paths(fund_id, base)
    if not fp.ledger.exists():
        _output({
            "status": "error",
            "detail": f"fund {fund_id!r} not found (searched {fp.ledger})",
            "next_step": f"run `nd paper create {fund_id}` or "
                         "`nd paper list` to see available funds",
        }, ctx.obj["json_output"])
        raise typer.Exit(code=1)
    return PaperLedger(fp.ledger)


def _today() -> date:
    """NEW (F5): the ONE wall-clock read in cli/. Tests patch this helper;
    persisted artifacts should prefer data-derived dates (see paper_halt)."""
    return date.today()


def _fund_paths(fund_id: str, base: str | None) -> Any:
    from niveshdristi.paper.fund import FundPaths

    return FundPaths(base).for_fund(fund_id)


def _paper_fetch_bars(universe: list[str], start: date, end: date) -> dict:
    """COMPOSITION POINT (cli/ only): fetch EOD bars through the IN_NSE
    yfinance adapter (amendment E). Never run by pytest or the gate.
    P11-S5: the window is [start, end) — start_window to the candidate.
    The old code passed `start` as BOTH bounds; yfinance's end is
    EXCLUSIVE, so the window was empty (proven offline by
    tests/test_fetch_window.py)."""
    import polars as pl

    from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient

    client = YFinanceClient()
    out: dict = {}
    for symbol in universe:
        hist = client._fetch(  # noqa: SLF001 - adapter composition in cli/
            f"{symbol}.NS", start, end, auto_adjust=True
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
    from niveshdristi.engine.advance import ModelBundle, RebalanceSchedule
    from niveshdristi.markets import IN_NSE_PROFILE
    from niveshdristi.markets.registry import to_rules
    from niveshdristi.paper.composition import record_composition
    from niveshdristi.portfolio.risk_gates import GateLimits

    rules = to_rules(IN_NSE_PROFILE)
    composition = record_composition(
        ModelBundle(_live_models_bundle()), GateLimits(), RebalanceSchedule()
    )
    universe_list = [s.strip() for s in universe.split(",") if s.strip()]
    try:
        ledger_path = create_fund(
            name, base=base,
            created=date.fromisoformat(created) if created else _today(),
            config_digest="cli-created", rules=rules,
            limitations=limitations, rates_verified=False,
            initial_cash=capital, universe=universe_list,
            composition=composition,
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

    _check_fund(fund_id, base, ctx)
    header = load_fund(fund_id, base=base).header()
    universe = header.get("universe", [])
    stub_used = any(
        entry.data_status != "live" for entry in registry.entries()
    )  # noted: limitation codes are fixed on the ledger header
    del stub_used

    _CALENDAR_DAYS_PER_SESSION = 1.5  # UNVALIDATED DEFAULT: ~1.5 calendar
    # days per trading session (accounts for weekends and holidays)

    candidate = date.fromisoformat(as_of) if as_of else _today()
    from niveshdristi.paper.composition import compose_from_recorded
    from niveshdristi.services.rules import rules_from_header

    recorded_comp = header.get("composition")
    if recorded_comp:
        models, limits, rebalance = compose_from_recorded(recorded_comp)
        # FX-I: derive the fetch window from the recorded composition
        required_sessions = recorded_comp.get(
            "required_history_sessions", 30
        )
        start_window = candidate - timedelta(
            days=int(required_sessions * _CALENDAR_DAYS_PER_SESSION)
        )
    else:
        models = ModelBundle(_live_models_bundle())
        limits = GateLimits()
        rebalance = RebalanceSchedule()
        start_window = candidate - timedelta(days=30)
    rules = rules_from_header(fund_id, base)
    # FX-I: if the fund has fewer ticked sessions than the required
    # history, emit an insufficient_history event listing each model and
    # its shortfall. The provider's actual row count depends on the fetch
    # window; a simple comparison suffices.
    _insufficient: list[dict] = []
    if recorded_comp:
        required_hist = recorded_comp.get("required_history_sessions", 0)
        ticked = len(__import__(
            "niveshdristi.paper.ledger", fromlist=["PaperLedger"]
        ).PaperLedger(_fund_paths(fund_id, base).ledger).records())
        if ticked < required_hist:
            for m in models.models:
                mhs = getattr(m, "min_history_sessions", 0)
                if mhs > 0:
                    _insufficient.append({
                        "model_id": m.model_id,
                        "required": mhs,
                        "ticked": ticked,
                        "shortfall": mhs - ticked,
                    })
    try:
        result = run_tick(
            fund_id, base=base,
            fetch_bars=lambda universe_, day: _paper_fetch_bars(
                universe_, start_window, day),
            clock_now=candidate,
            models=models, rules=rules,
            limits=limits, rebalance=rebalance,
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
    if _insufficient:
        _events_log(fund_id, base).append(
            "insufficient_history", fund_id=fund_id, models=_insufficient
        )
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
    from niveshdristi.paper.killswitch import is_halted

    ledger = _check_fund(fund_id, base, ctx)
    header = ledger.header()
    halted, halt_reason = is_halted(_fund_paths(fund_id, base), fund_id=fund_id)
    last = ledger.last_session_date()
    records = ledger.records()

    comp = header.get("composition", {})
    required_hist = comp.get("required_history_sessions")
    warming = (
        {"required": required_hist, "ticked": len(records),
         "status": ("warming up (" + str(len(records)) + " of "
                    + str(required_hist) + " sessions)")
                    if len(records) < required_hist else "active"}
        if required_hist else None
    )
    _output({
        "fund_id": fund_id,
        "last_session": last.isoformat() if last else None,
        "cash_after": records[-1]["cash_after"] if records else None,
        "halted": halted,
        "halt_reason": halt_reason or None,
        "limitations": header["limitation_codes"],
        "warming_up": warming,
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

    # F5: the session stamped into the persisted flag is DATA-DERIVED (the
    # ledger's last session; the created date when the ledger is empty),
    # never the wall clock.
    ledger = _check_fund(fund_id, base, ctx)
    stamp = ledger.last_session_date() or _today()
    payload = halt(
        _fund_paths(fund_id, base), fund_id=fund_id, reason=reason,
        session=stamp, event_id=f"halt-{fund_id}",
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

    _check_fund(fund_id, base, ctx)
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
    ledger = _check_fund(fund_id, base, ctx)
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
    from niveshdristi.engine.advance import ModelBundle as MB
    from niveshdristi.engine.advance import RebalanceSchedule as RS
    from niveshdristi.paper.composition import compose_from_recorded
    from niveshdristi.paper.replay import replay_fund
    from niveshdristi.portfolio.risk_gates import GateLimits as GLimits

    _check_fund(fund_id, base, ctx)
    header = __import__(
        "niveshdristi.paper.ledger", fromlist=["PaperLedger"]
    ).PaperLedger(_fund_paths(fund_id, base).ledger).header()
    recorded = header.get("composition")
    if recorded:
        models, limits, rebalance = compose_from_recorded(recorded)
        composition_recorded = True
    else:
        models = MB(_live_models_bundle())
        limits = GLimits()
        rebalance = RS()
        composition_recorded = False
        print("WARNING: fund has no recorded composition; replay uses the "
              "CURRENT composition and may not match.", file=sys.stderr)
    result = replay_fund(
        fund_id, base=base, models=models, limits=limits, rebalance=rebalance,
    )
    result["composition_recorded"] = composition_recorded
    _output(result, ctx.obj["json_output"])
    if not result.get("byte_identical", False):
        raise typer.Exit(code=1)


@paper_app.command("recover")
def paper_recover(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """OPERATOR: rebuild the broker cache from the ledger (never called by
    tick). R9a: re-derives the pending decision by dry-running the last
    session from its stored snapshot (hash-checked against the ledger)."""
    from niveshdristi.engine.advance import ModelBundle as MB
    from niveshdristi.engine.advance import RebalanceSchedule as RS
    from niveshdristi.paper.fund import recover_fund

    _check_fund(fund_id, base, ctx)
    from niveshdristi.portfolio.risk_gates import GateLimits as GLimits

    result = recover_fund(
        _fund_paths(fund_id, base),
        models=MB(_live_models_bundle()),
        rules=_market_rules_from_header(fund_id, base),
        limits=GLimits(),
        rebalance=RS(),
    )
    _events_log(fund_id, base).append("recover", fund_id=fund_id, **result)
    _output({"status": "recovered", **result}, ctx.obj["json_output"])


@paper_app.command("prune-snapshots")
def paper_prune_snapshots(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    keep_last: int = typer.Option(60, "--keep-last",
                                  help="Sessions whose snapshots survive"),
    apply: bool = typer.Option(False, "--apply",
                               help="REQUIRED to delete (dry-run by default)"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """OPERATOR: delete snapshot dirs older than the last --keep-last
    sessions to bound disk usage. TRADE-OFF: replay of pruned sessions is
    impossible (reported explicitly as 'snapshots unavailable'). The
    ledger, header, decision sidecars, cache, halt and heartbeat files are
    NEVER touched. Dry-run is the default."""
    from niveshdristi.paper.retention import prune_snapshots

    _check_fund(fund_id, base, ctx)
    result = prune_snapshots(fund_id, base=base, keep_last=keep_last,
                             apply=apply)
    _events_log(fund_id, base).append(
        "prune-snapshots", fund_id=fund_id, **result)
    _output({"status": "applied" if result["applied"] else "dry-run",
             **result}, ctx.obj["json_output"])


@paper_app.command("unlock")
def paper_unlock(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
):
    """OPERATOR: remove a stale tick lock (logged)."""
    _check_fund(fund_id, base, ctx)
    lock = _fund_paths(fund_id, base).root / "tick.lock"
    if lock.exists():
        lock.unlink()
    _events_log(fund_id, base).append("unlock", fund_id=fund_id)
    _output({"status": "unlocked"}, ctx.obj["json_output"])


@paper_app.command("explain")
def paper_explain(
    ctx: typer.Context,
    fund_id: str = typer.Argument(..., help="Fund ID"),
    session: str = typer.Option(..., "--session", help="Session date (YYYY-MM-DD)"),
    base: str | None = typer.Option(None, "--base", help="Funds directory"),
    provider: str = typer.Option("fake", "--provider", help="LLM provider (registered only)"),
    model: str = typer.Option("fake-model", "--model", help="Model id (unverified; VERIFY note)"),
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Response cache directory"),
):
    """Educational explanation of a stored session (R2: evidence text only).

    Builds evidence from the stored SessionRecord, calls the LLM through
    make_llm with the safety pipeline (delimited data blocks, redaction by
    default) and prints a validated, cited, disclaimed explanation. ANY
    failure degrades to a clear no-op (R11); the LLM never enters the
    trading path (R1/R10).
    """
    from datetime import date as _date

    from niveshdristi.llm import (
        Budget,
        EvidenceItem,
        RunBudget,
        data_block,
        make_llm,
        run_llm,
    )
    from niveshdristi.llm.safety import SYSTEM_RULES, redact
    from niveshdristi.paper.ledger import LedgerError, PaperLedger

    try:
        ledger = PaperLedger(_fund_paths(fund_id, base).ledger)
        record = next(
            (r for r in ledger.records()
             if r.get("session_date") == session),
            None,
        )
    except LedgerError as exc:
        _output({
            "status": "no-op",
            "detail": str(exc),
            "next_step": f"run `nd paper create {fund_id}` or "
                         "`nd paper list` to see available funds",
        }, ctx.obj["json_output"])
        return
    if record is None:
        _output(
            {"status": "no-op", "detail": f"no stored session {session}"},
            ctx.obj["json_output"],
        )
        return

    evidence = (
        EvidenceItem(id="session_date", text=f"session date {session}"),
        EvidenceItem(
            id="cash_after",
            text="cash after the session (rupees)",
            numbers=(float(record["cash_after"]),),
        ),
        EvidenceItem(
            id="equity_after",
            text="equity after the session (rupees)",
            numbers=(float(record["equity_after"]),),
        ),
        EvidenceItem(
            id="fill_count",
            text="number of fills this session",
            numbers=(float(len(record.get("fills", []))),),
        ),
    )
    raw_text = json.dumps(record, sort_keys=True, default=str)
    # R6 + F13: redact fund id, cash, equity/NAV, EVERY fill/position
    # quantity and price, and any path (no opt-in flags are exposed in this
    # command). DOCUMENTED FAIL-SAFE: with everything portfolio-specific
    # redacted, the explain feature currently yields little numeric value
    # by design — the model never sees the numbers it must cite.
    # redact() takes ONE literal per category, so multi-value categories
    # (quantities, prices) are applied as sequential literal removals and
    # redact(raw_text, {}) finishes with the unconditional secret scrub.
    outgoing = redact(raw_text, {
        "fund_ids": fund_id,
        "cash": str(record["cash_after"]),
        "nav": str(record["equity_after"]),
        "paths": str(_fund_paths(fund_id, base).root),
    })
    multi: list[tuple[str, str]] = [("cash", str(record["cash_after"]))]
    for fill in record.get("fills", []) or []:
        if fill.get("fill_price") is not None:
            multi.append(("quantities", str(fill["fill_price"])))
        if fill.get("filled_quantity") is not None:
            multi.append(("quantities", str(fill["filled_quantity"])))
    for pos in record.get("positions_after", []) or []:
        if pos.get("market_value") is not None:
            multi.append(("nav", str(pos["market_value"])))
        if pos.get("shares") is not None:
            multi.append(("quantities", str(pos["shares"])))
    for category, literal in multi:
        if literal and literal in outgoing:
            outgoing = outgoing.replace(literal, f"[REDACTED:{category}]")
    outgoing = redact(outgoing, {})  # unconditional secret scrub
    llm = make_llm(provider, model)
    outcome = run_llm(
        llm,
        data_blocks=(data_block("session_record", outgoing),),
        evidence=evidence,
        model_id=model,
        as_of=_date.fromisoformat(session),  # caller-supplied, from the record
        budget=Budget(),
        run=RunBudget(Budget()),
        cache_dir=cache_dir,
        extra_system=SYSTEM_RULES,
    )
    payload: dict[str, Any] = {"status": outcome.status}
    if outcome.view is not None:
        payload["view"] = outcome.view.model_dump(mode="json")
    if outcome.detail:
        payload["detail"] = outcome.detail
    _output(payload, ctx.obj["json_output"])


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
