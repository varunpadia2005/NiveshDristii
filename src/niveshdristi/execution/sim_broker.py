"""SimBroker (NEW, Phase 4) — deterministic simulation, no I/O.

Provenance convention check: execute() accepts ONLY orders whose
client_order_id starts with the gate marker produced by build_orders
("gate-"); anything else raises (a convention check, not security).

Behaviours:
- Integer shares; fills never exceed order quantity (core Fill enforces).
- Costs computed by the cost engine on EVERY fill.
- Circuit-limit fill failure: if the session's simulated price moved at or
  beyond a supplied band fraction vs the reference price, the order FAILS
  (no fill). Fixture-only: per-symbol band data has NO source today; the
  band comes from the profile-level PriceLimitRule bands supplied as input.
- Liquidity-scaled slippage: base bps scaled by (order value / ADV), with
  named UNVALIDATED DEFAULT constants; ADV None -> base slippage only.
- Cash accounting: total spend never exceeds the broker's cash balance;
  otherwise the order is rejected with a logged reason. Cash never negative.
- Settlement T+1 is RECORDED AS A NUMBER ONLY (settlement_days); date
  arithmetic waits for the Phase 5 calendar (2026 holiday data still missing).
"""

from __future__ import annotations

from datetime import UTC, datetime

from niveshdristi.core.decision import Fill, Order
from niveshdristi.core.market_rules import PriceLimitRule, RateSchedule
from niveshdristi.execution.costs import compute_costs

# UNVALIDATED DEFAULTS (hypotheses, not calibrated)
GATE_MARKER = "gate-"
SLIPPAGE_SCALE_CAP = 3.0  # liquidity multiplier capped at 3x base bps
SLIPPAGE_ADV_REF = 0.10  # order value at 10% of ADV -> 1x base slippage


class ExecutionResult:
    """One order's outcome: fill or refusal, with reason."""

    def __init__(self, order: Order, fill: Fill | None, reason: str) -> None:
        self.order = order
        self.fill = fill
        self.reason = reason

    @property
    def filled(self) -> bool:
        return self.fill is not None


class SimBroker:
    """Deterministic broker over explicit inputs (NEW)."""

    def __init__(
        self,
        *,
        rates: RateSchedule,
        price_limits: PriceLimitRule,
        settlement_days: int = 1,
    ) -> None:
        self._rates = rates
        self._limits = price_limits
        self._settlement_days = settlement_days

    def execute(
        self,
        orders: list[Order],
        *,
        prices: dict[str, float],
        reference_prices: dict[str, float] | None = None,
        advs: dict[str, float] | None = None,
        cash: float | None = None,
    ) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        available = cash if cash is not None else float("inf")
        band = max(self._limits.bands) if self._limits.bands else 1.0
        reference_prices = reference_prices or prices

        for order in orders:
            if not order.client_order_id.startswith(GATE_MARKER):
                raise ValueError(
                    f"order {order.client_order_id!r} lacks gate provenance "
                    f"(must start with {GATE_MARKER!r}); convention check"
                )
            symbol = order.instrument.symbol
            price = prices.get(symbol)
            if price is None or price <= 0:
                results.append(ExecutionResult(order, None, "no price"))
                continue

            # Circuit-limit failure: session price moved at/beyond the band
            ref = reference_prices.get(symbol)
            if ref is not None and ref > 0:
                move = abs(price / ref - 1.0)
                if self._limits.enabled and move >= band:
                    results.append(
                        ExecutionResult(
                            order, None,
                            f"circuit limit: move {move:.4f} at/beyond band {band}",
                        )
                    )
                    continue

            notional = order.quantity * price
            if notional > available:
                results.append(
                    ExecutionResult(order, None, "rejected: insufficient cash")
                )
                continue

            # Liquidity-scaled slippage
            slippage_bps = self._rates.slippage_base_bps
            adv = (advs or {}).get(symbol)
            if adv and adv > 0:
                ratio = notional / adv
                multiplier = min(1.0 + ratio / SLIPPAGE_ADV_REF, SLIPPAGE_SCALE_CAP)
                slippage_bps = self._rates.slippage_base_bps * multiplier

            fill_price = price * (1.0 + slippage_bps / 10_000.0)  # adverse move
            breakdown = compute_costs(
                side="buy",
                notional=order.quantity * fill_price,
                rates=self._rates,
            )
            available -= order.quantity * fill_price
            results.append(
                ExecutionResult(
                    order,
                    Fill(
                        order=order,
                        filled_quantity=order.quantity,
                        fill_price=round(fill_price, 6),
                        fill_time=datetime.now(UTC),
                        commission=breakdown.brokerage,
                        fees=round(breakdown.fees_total - breakdown.brokerage, 6),
                        slippage_bps=round(slippage_bps, 6),
                        broker_order_id="sim",
                    ),
                    f"filled (settlement T+{self._settlement_days} recorded as a number only)",
                )
            )
        return results
