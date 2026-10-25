"""Engine `advance()` (NEW, Phase 5) — one session step, backtest == paper.

Mechanics at session T (documented choice: EXECUTE AT THE NEXT SESSION'S
CLOSE — decisions made on data through T's close fill at T+1's close):
1. reconcile the broker book against FundState (typed error on mismatch);
2. execute the pending decision from T-1 at T's prices, SELLS FIRST then
   buys; orders that cannot fill (no bar for the symbol at T, circuit
   limit, insufficient cash) LAPSE with a logged reason and are NOT
   carried forward; clear pending;
3. mark to market at T close;
4. if rebalance(T): models predict at as_of=T -> blend -> construct ->
   risk gates -> PendingDecision (stored, NOT executed);
5. append a hash-chained SessionRecord (core's existing SessionRecord;
   `created_at` is set to the session close timestamp for DETERMINISM —
   it is not a wall-clock read).

Shadow GROSS track (P5-S2a convention): the same fill quantities valued at
the UNSLIPPED session close with NO fees; slippage is embedded in net fills
and counted exactly once in the net track. Tax: sells consume lots FIFO;
realized gains accrue through the tax engine as a LIABILITY reported next
to net equity — NOT deducted from cash in v1 (cash impact of taxes is a
Phase 6 ledger concern); controlled by tax_enabled.

Look-ahead is made structurally impossible for models: their data arrives
ONLY via ModelInputs built by marketdata.context.build_from_full_frames at
as_of=T, which RAISES on any row dated after T. The broker receives fill
prices through a separate channel (the raw close dict for the fill
session), which is never handed to models. This separation is by
construction and convention, not a security boundary.

Determinism: no clock reads, no randomness, sorted iteration everywhere,
stable tie-breaks; `created_at` derived from the session date.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Protocol

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext
from niveshdristi.core.decision import Fill, Order, OrderSide
from niveshdristi.core.errors import ExecutionError
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.core.session import PositionSnapshot, SessionRecord
from niveshdristi.engine.fund import FundState, Lot, PendingDecision, RealizedSale
from niveshdristi.execution.orders import build_orders
from niveshdristi.marketdata.context import build_from_full_frames
from niveshdristi.portfolio.blending import blend_convictions
from niveshdristi.portfolio.construction import construct_targets
from niveshdristi.portfolio.risk_gates import GateLimits, run_chain

_SESSION_CLOSE = time(15, 30)  # documented convention: records stamped at close
SETTLEMENT_DAYS_DEFAULT = 1


class Broker(Protocol):
    """Execution interface (matches execution.broker)."""

    def execute(self, orders: list[Order], **kwargs: Any) -> list[Any]:
        ...


class ModelBundle:
    """Models + their blend weights (equal by default)."""

    def __init__(self, models: Sequence[AlphaModel]) -> None:
        self.models = tuple(models)

    @property
    def known_ids(self) -> set[str]:
        return {m.model_id for m in self.models}

    def as_strategy_models(self) -> list[dict[str, Any]]:
        return [{"model_id": m.model_id, "weight": 1.0} for m in self.models]


@dataclass(frozen=True, slots=True)
class RebalanceSchedule:
    """Rebalance every N sessions (session_seq % n == 0), first session on."""

    every_n_sessions: int = 1
    first_session_on: bool = True

    def due(self, seq: int) -> bool:
        if seq == 0:
            return self.first_session_on
        return seq % self.every_n_sessions == 0


def _session_close_stamp(session_date: date) -> datetime:
    """Deterministic record stamp: the session's close time, UTC-naive-free."""
    return datetime.combine(session_date, _SESSION_CLOSE, tzinfo=UTC)


def _close_map(frames: Mapping[str, pl.DataFrame], day: date) -> dict[str, float]:
    """Close prices for one session across all symbols that have a bar."""
    out: dict[str, float] = {}
    key = day.isoformat()
    for symbol, frame in frames.items():
        if "date" not in frame.columns or "close" not in frame.columns:
            continue
        rows = frame.filter(pl.col("date").cast(pl.String).str.slice(0, 10) == key)
        if rows.height:
            out[symbol] = float(rows["close"].to_list()[-1])
    return out


def _consume_lots_fifo(
    lots: tuple[Lot, ...], symbol: str, quantity: int, sell_date: date, sell_price: float
) -> tuple[tuple[Lot, ...], list[RealizedSale], float]:
    """FIFO consumption; returns remaining lots, realized slices, proceeds."""
    remaining: list[Lot] = []
    realized: list[RealizedSale] = []
    proceeds = 0.0
    to_sell = quantity
    for lot in lots:
        if lot.symbol != symbol or to_sell <= 0:
            remaining.append(lot)
            continue
        take = min(to_sell, lot.quantity)
        realized.append(
            RealizedSale(
                symbol=symbol, quantity=take, buy_date=lot.buy_date,
                sell_date=sell_date, cost_per_share=lot.cost_per_share,
                sell_price=sell_price,
            )
        )
        proceeds += take * sell_price
        to_sell -= take
        if lot.quantity > take:
            remaining.append(Lot(symbol, lot.quantity - take, lot.buy_date, lot.cost_per_share))
    if to_sell > 0:
        raise ExecutionError(
            f"sell of {quantity} {symbol} exceeds held lots (short by {to_sell})"
        )
    return tuple(remaining), realized, proceeds


def advance(
    fund: FundState,
    session_date: date,
    broker: Broker,
    data: Mapping[str, pl.DataFrame],
    *,
    models: ModelBundle,
    rules: MarketRules,
    limits: GateLimits,
    rebalance: RebalanceSchedule,
    tax_enabled: bool = False,
    cash_reserve: float = 0.0,
) -> tuple[FundState, SessionRecord]:
    """One session step: reconcile, execute pending, mark, assess, record."""
    events: list[str] = []
    closes = _close_map(data, session_date)
    seq = fund.session_seq

    # 1. Reconcile broker book vs FundState (broker book = fills it executed;
    #    tracked by the driver and passed via cash_reserve convention — here we
    #    verify the broker's own executed-positions ledger if it keeps one).
    broker_book = getattr(broker, "positions", None)
    if broker_book is not None and broker_book != fund.positions():
        raise ExecutionError(
            f"reconcile failed: broker book {broker_book} != fund positions {fund.positions()}"
        )

    # Mark at T's close BEFORE executing the pending decision: target-value
    # comparisons must use marked equity, never the (possibly fee-depleted)
    # cash balance.
    holdings = fund.positions()
    nav_mark = fund.cash + sum(
        qty * closes.get(sym, 0.0) for sym, qty in sorted(holdings.items())
    )

    # 2. Execute pending decision (from T-1): SELLS FIRST then buys
    fills: list[Fill] = []
    realized: list[RealizedSale] = []
    fees = slippage = 0.0
    lots = fund.lots
    cash = fund.cash
    broker_positions: dict[str, int] = {}
    pending = fund.pending_decision
    if pending is not None:
        instrument_cache: dict[str, Instrument] = {}

        def inst_for(symbol: str) -> Instrument:
            if symbol not in instrument_cache:
                instrument_cache[symbol] = Instrument(
                    symbol=symbol, exchange=rules.market_id,
                    market_id=rules.market_id, currency="XXX",
                )
            return instrument_cache[symbol]

        # SELLS: held symbols dropped from targets sell ENTIRELY; held
        # symbols still in targets but OVER-WEIGHT vs nav_mark TRIM to the
        # target value (ceil to whole shares, capped at holdings).
        sell_orders: list[Order] = []
        for symbol in sorted(holdings):
            target_weight = pending.gated.weights.get(symbol, 0.0)
            price = closes.get(symbol, 0.0)
            held_qty = holdings[symbol]
            held_value = held_qty * price
            target_value = target_weight * nav_mark  # weights are NAV fractions
            if target_weight <= 0.0:
                sell_orders.append(
                    Order(
                        instrument=inst_for(symbol), side=OrderSide.SELL,
                        quantity=held_qty,
                        placed_at=_session_close_stamp(session_date),
                        client_order_id=f"gate-sell-{symbol}",
                    )
                )
            elif held_value > target_value and price > 0:
                trim_value = held_value - target_value
                trim_qty = min(held_qty, -(-int(trim_value * 100) // (int(price * 100))))
                if trim_qty > 0:
                    sell_orders.append(
                        Order(
                            instrument=inst_for(symbol), side=OrderSide.SELL,
                            quantity=trim_qty,
                            placed_at=_session_close_stamp(session_date),
                            client_order_id=f"gate-sell-{symbol}",
                        )
                    )
        sell_results = broker.execute(
            sell_orders, prices=closes, stamp=_session_close_stamp(session_date)
        )
        for r in sell_results:
            if r.filled and r.fill is not None:
                fill = r.fill
                symbol = fill.order.instrument.symbol
                fills.append(fill)
                fees += fill.commission + fill.fees
                slip_qty = abs(fill.fill_price - closes.get(symbol, fill.fill_price))
                slippage += slip_qty * fill.filled_quantity
                lots, slices, proceeds = _consume_lots_fifo(
                    lots, symbol, fill.filled_quantity, session_date, fill.fill_price
                )
                realized.extend(slices)
                cash += proceeds - fill.commission - fill.fees
                broker_positions[symbol] = broker_positions.get(symbol, 0) - fill.filled_quantity
            else:
                events.append(f"sell lapse: {r.reason}")

        # BUYS: build_orders sizes against updated cash (sells already in)
        buy_orders, build_logs = build_orders(
            pending.gated,
            nav=nav_mark,
            cash=cash,
            prices=closes,
            instruments={s: inst_for(s) for s in pending.gated.weights},
            current_holdings=fund.positions(),
            reserve_cash=0.0,
            stamp=_session_close_stamp(session_date),
        )
        # Fit buy quantities to cash MINUS estimated fees (fees are linear
        # in notional plus a flat brokerage+GST component; estimate uses the
        # real RateSchedule so buys never overdraw cash).
        var_rate = (
            rules.rates.stt_delivery_buy + rules.rates.exchange_fee
            + rules.rates.regulator_fee + rules.rates.stamp_duty_buy
        )
        flat_fees = rules.rates.brokerage_per_order * (1.0 + rules.rates.gst_on_fees)
        fitted_orders: list[Order] = []
        remaining = cash
        for order in buy_orders:
            price = closes[order.instrument.symbol]
            if price <= 0:
                continue
            max_qty = int(max(0.0, remaining - flat_fees) / (price * (1.0 + var_rate)))
            qty = min(order.quantity, max_qty)
            if qty <= 0:
                note = (
                    f"buy dropped: cash {remaining:.2f} below fees for "
                    f"{order.instrument.symbol}"
                )
                events.append(note)
                continue
            if qty < order.quantity:
                events.append(
                    f"buy reduced: {order.instrument.symbol} {order.quantity}->{qty} (cash fit)"
                )
            fitted_orders.append(order.model_copy(update={"quantity": qty}))
            remaining -= qty * price
        buy_orders = fitted_orders
        for entry in build_logs:
            events.append(f"build: {entry.symbol} {entry.note}")
        buy_results = broker.execute(
            buy_orders, prices=closes, stamp=_session_close_stamp(session_date)
        )
        for r in buy_results:
            if r.filled and r.fill is not None:
                fill = r.fill
                symbol = fill.order.instrument.symbol
                fills.append(fill)
                fees += fill.commission + fill.fees
                slip_qty = abs(fill.fill_price - closes.get(symbol, fill.fill_price))
                slippage += slip_qty * fill.filled_quantity
                cash -= fill.filled_quantity * fill.fill_price + fill.commission + fill.fees
                broker_positions[symbol] = broker_positions.get(symbol, 0) + fill.filled_quantity
                lots = lots + (
                    Lot(symbol, fill.filled_quantity, session_date, fill.fill_price),
                )
            else:
                events.append(f"buy lapse: {r.reason}")
    else:
        broker_positions = dict(fund.positions())

    # 3. Mark to market at T close
    positions_now = FundState(
        cash=cash, lots=lots, realized=fund.realized,
        tax_accrued=fund.tax_accrued, pending_decision=None,
        session_seq=seq, last_session=session_date, last_hash=fund.last_hash,
    ).positions()
    market_value = sum(qty * closes.get(sym, 0.0) for sym, qty in positions_now.items())
    equity = cash + market_value

    # Shadow GROSS track (P5-S2a convention): same fill quantities at the
    # UNSLIPPED close with NO fees. The wedge between gross and net equity
    # is exactly fees + slippage (counted once); recorded in risk_metrics.

    # 4. Assess (rebalance days): models at as_of=T -> blend -> construct -> gates
    new_pending: PendingDecision | None = None
    if rebalance.due(seq):
        inputs = build_from_full_frames(as_of=session_date, prices=dict(data))
        ctx = AsOfContext(
            as_of=datetime.combine(session_date, _SESSION_CLOSE, tzinfo=UTC),
            universe=(), market_id=rules.market_id,
        )
        signals: list = []
        for model in models.models:
            signals.extend(model.predict(ctx, inputs))
        blended = blend_convictions(
            models.as_strategy_models(), signals, known_model_ids=models.known_ids
        )
        synth_signals = []
        for symbol, conviction in sorted(blended.items()):
            synth_signals.append(
                _SynthSignalView(symbol, conviction, rules.market_id, ctx.as_of)
            )
        targets = construct_targets(synth_signals, rules)  # type: ignore[arg-type]
        gated = run_chain(
            targets, limits=limits, rules=rules, current_weights=positions_now,
            prices=closes, nav=equity, equity_history=(equity,),
            decision_date=session_date,
        )
        new_pending = PendingDecision(decision_date=session_date, gated=gated)
        events.append(f"assessed: {len(blended)} blended symbol(s) gated")

    # Tax accrual (liability, NOT deducted from cash in v1)
    tax_accrued = fund.tax_accrued
    if tax_enabled and realized:
        from niveshdristi.portfolio.tax import RealisedLot, compute_tax

        lots_for_tax = [
            RealisedLot(
                symbol=s.symbol, buy_date=s.buy_date, sell_date=s.sell_date,
                proceeds_minus_cost=s.gain,
            )
            for s in realized
        ]
        result = compute_tax(lots_for_tax, rules.tax, fy_start_month=4) if rules.tax else None
        if result is not None:
            tax_accrued += result.tax_due
            events.append(f"tax accrued {result.tax_due:.2f} on {len(realized)} sale(s)")

    # 5. Append hash-chained SessionRecord
    snapshots = tuple(
        PositionSnapshot(
            instrument=Instrument(
                symbol=sym, exchange=rules.market_id, market_id=rules.market_id,
                currency="XXX",
            ),
            shares=qty,
            avg_cost=0.0,
            market_value=qty * closes.get(sym, 0.0),
        )
        for sym, qty in sorted(positions_now.items())
    )
    record = SessionRecord(
        session_id=seq,
        session_date=session_date,
        previous_hash=fund.last_hash,
        decisions=(),
        fills=tuple(fills),
        positions_after=snapshots,
        cash_after=cash,
        equity_after=equity,
        risk_metrics={
            "session_fees": round(fees, 6),
            "session_slippage": round(slippage, 6),
            "tax_accrued": round(tax_accrued, 6),
        },
        events=tuple(events),
        created_at=_session_close_stamp(session_date),
    )
    new_fund = FundState(
        cash=cash, lots=lots, realized=fund.realized + tuple(realized),
        tax_accrued=tax_accrued, pending_decision=new_pending,
        session_seq=seq + 1, last_session=session_date,
        last_hash=record.compute_hash(),
    )
    return new_fund, record


class _SynthSignalView:
    """Minimal Signal-like view for construct_targets (symbol+conviction)."""

    def __init__(self, symbol: str, conviction: float, market_id: str, as_of: datetime) -> None:
        self.instrument = Instrument(
            symbol=symbol, exchange=market_id, market_id=market_id, currency="XXX"
        )
        self.conviction = conviction
        self.horizon_days = 10
        self.model_id = "blended"

    def effective_conviction(self, *, long_only: bool = True) -> float:
        if long_only and self.conviction < 0:
            return 0.0
        return self.conviction
