"""Backtest driver (NEW, Phase 5) — advance() looped over the calendar.

BacktestResult REQUIRES a DataLimitations object (constructor contract
modelled in tests/test_alpha.py). The driver AUTO-ADDS limitation codes it
can determine and never removes caller codes; promotable stays False while
any code is present. NOT a real-data run: synthetic frames only; a
real-data backtest would be an opt-in tools/ script outside pytest/gate.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.core.limitations import DataLimitations
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.engine.advance import FundState, ModelBundle, RebalanceSchedule, advance
from niveshdristi.engine.calendar import DataCalendar
from niveshdristi.portfolio.risk_gates import GateLimits

AUTO_CODES_BASE = frozenset({
    "derived_calendar",           # data calendar, not an official one
    "adjusted_price_basis",       # PRICE-BASIS DECISION A
    "corporate_actions_unavailable",
    "price_level_rules_on_adjusted",
})


class BacktestResult(BaseModel):
    """Frozen backtest output; limitations required, banner non-droppable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitations: DataLimitations  # REQUIRED
    net_equity_curve: tuple[tuple[date, float], ...]
    gross_equity_curve: tuple[tuple[date, float], ...]
    fees_total: float
    slippage_total: float
    tax_accrued: float
    trade_count: int
    clamp_count: int
    calendar_source: str = "derived-from-prices"
    record_hashes: tuple[str, ...] = ()

    @property
    def drag(self) -> float:
        """Gross minus net over the curve (fees + slippage counted once)."""
        if not self.net_equity_curve:
            return 0.0
        return self.gross_equity_curve[-1][1] - self.net_equity_curve[-1][1]

    @property
    def drag_bps(self) -> float:
        first = self.gross_equity_curve[0][1] if self.gross_equity_curve else 0.0
        if first == 0:
            return 0.0
        return self.drag / first * 10_000

    @property
    def banner(self) -> str | None:
        return self.limitations.banner


def run_backtest(
    frames: dict,
    *,
    models: ModelBundle,
    rules: MarketRules,
    limits: GateLimits,
    rebalance: RebalanceSchedule,
    initial_cash: float = 1_000_000.0,
    broker=None,
    rates_verified: bool = False,
    universe_approximate: bool = False,
    stub_models_used: bool = False,
    benchmark_used: bool = False,
    extra_limitations: frozenset[str] = frozenset(),
) -> BacktestResult:
    """Drive advance() over the data-derived calendar (NEW)."""
    from niveshdristi.core.market_rules import PriceLimitRule

    if broker is None:
        from niveshdristi.execution.sim_broker import SimBroker

        broker = SimBroker(
            rates=rules.rates, price_limits=PriceLimitRule(enabled=False)
        )
    calendar = DataCalendar.from_frames(frames)
    sessions = list(calendar.sessions())
    fund = FundState(cash=initial_cash)
    net_curve: list[tuple[date, float]] = []
    gross_curve: list[tuple[date, float]] = []
    fees_total = slippage_total = 0.0
    tax_total = 0.0
    trade_count = 0
    clamp_count = 0
    hashes: list[str] = []
    prev_hash = "0" * 64

    for session_date in sessions:
        fund, record = advance(
            fund, session_date, broker, frames,
            models=models, rules=rules, limits=limits,
            rebalance=rebalance, tax_enabled=True,
        )
        linked = record.model_copy(update={"previous_hash": prev_hash})
        prev_hash = linked.compute_hash()
        hashes.append(prev_hash)
        fees_total += float(record.risk_metrics.get("session_fees", 0.0))
        slippage_total += float(record.risk_metrics.get("session_slippage", 0.0))
        tax_total = fund.tax_accrued
        trade_count += len(record.fills)

        net_curve.append((session_date, record.equity_after))
        wedge = fees_total + slippage_total
        gross_curve.append((session_date, record.equity_after + wedge))

    codes: set[str] = set(AUTO_CODES_BASE)
    if not rates_verified:
        codes.add("rates_unverified")
    if universe_approximate:
        codes.update({"approximate_universe", "survivorship_universe"})
    if stub_models_used:
        codes.add("stub_models_used")
    if benchmark_used:
        codes.add("benchmark_not_tri")
    codes |= set(extra_limitations)  # caller may ADD, never remove autos
    return BacktestResult(
        limitations=DataLimitations(CODES=frozenset(codes)),
        net_equity_curve=tuple(net_curve),
        gross_equity_curve=tuple(gross_curve),
        fees_total=round(fees_total, 6),
        slippage_total=round(slippage_total, 6),
        tax_accrued=round(tax_total, 6),
        trade_count=trade_count,
        clamp_count=clamp_count,
        record_hashes=tuple(hashes),
    )
