"""Gate-chain order building + Broker protocol (NEW, Phase 4).

build_orders accepts ONLY GatedTargets (the risk-gate chain output; the
private construction token guarantees provenance as a CONVENTION CHECK) and
converts target weights + NAV + prices + current holdings into INTEGER-share
core Orders. Floor to integer shares; never spend more than available cash;
zero-quantity orders are dropped with a logged reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from niveshdristi.core.decision import Order, OrderSide, OrderType
from niveshdristi.core.instrument import Instrument
from niveshdristi.portfolio.risk_gates import GatedTargets


class BuildLog:
    """Simple immutable log entry for order building."""

    def __init__(self, symbol: str, note: str) -> None:
        self.symbol = symbol
        self.note = note

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"BuildLog({self.symbol}: {self.note})"


def build_orders(
    gated: GatedTargets,
    *,
    nav: float,
    cash: float,
    prices: dict[str, float],
    instruments: dict[str, Instrument],
    current_holdings: dict[str, int],
    reserve_cash: float = 0.0,
    stamp: datetime | None = None,
) -> tuple[list[Order], list[BuildLog]]:
    """GatedTargets -> integer-share Orders (BUY delta only in v1 long-only).

    Deterministic: symbols processed in sorted order. Available spend is
    tracked so total buy spend never exceeds cash - reserve_cash.
    """
    orders: list[Order] = []
    logs: list[BuildLog] = []
    available = cash - reserve_cash
    now = stamp if stamp is not None else datetime.now(UTC)

    for symbol in sorted(gated.weights):
        price = prices.get(symbol)
        if price is None or price <= 0:
            logs.append(BuildLog(symbol, "dropped: no/invalid price"))
            continue
        target_value = gated.weights[symbol] * nav
        current_value = current_holdings.get(symbol, 0) * price
        delta_value = target_value - current_value
        if delta_value <= 0:
            note = f"dropped: target {target_value:.2f} <= current {current_value:.2f}"
            logs.append(BuildLog(symbol, note))
            continue
        raw_qty = delta_value / price
        qty = int(raw_qty)  # floor to integer shares
        if qty <= 0:
            logs.append(BuildLog(symbol, f"dropped: floored quantity 0 (raw {raw_qty:.4f})"))
            continue
        cost = qty * price
        if cost > available:
            qty = int(available / price)
            cost = qty * price
            if qty <= 0:
                logs.append(BuildLog(symbol, "dropped: insufficient cash after floor"))
                continue
            logs.append(BuildLog(symbol, f"reduced to {qty}: cash limit"))
        available -= cost
        orders.append(
            Order(
                instrument=instruments[symbol],
                side=OrderSide.BUY,
                quantity=qty,
                order_type=OrderType.MARKET,
                placed_at=now,
                client_order_id=f"gate-{symbol}",
                decision_id=None,
            )
        )
    return orders, logs


class Broker(Protocol):
    """Execution protocol: accepts ONLY orders with gate provenance."""

    def execute(self, orders: list[Order], *, prices: dict[str, float]) -> list[object]:
        ...
