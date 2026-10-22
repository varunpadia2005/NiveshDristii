"""Decision, Order, Fill — portfolio construction and execution primitives."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class Decision:
    """
    Portfolio construction decision for a single instrument.

    Created by the portfolio construction layer from blended signals + risk gates.
    Passed to execution layer for order generation.

    Attributes:
        instrument: Target instrument
        target_weight: Target portfolio weight (0.0 to 1.0 for long-only)
        target_shares: Target share count (integer, computed from weight + price)
        current_shares: Current share count in portfolio
        delta_shares: Shares to trade (target - current)
        side: OrderSide.BUY or OrderSide.SELL (or None if delta_shares == 0)
        reason: Human-readable explanation (e.g., "signal blend + risk gate clamp")
        signal_contributions: Breakdown of contributing signals {model_id: conviction}
        risk_gate_clamp: If True, risk gates modified the raw target
        clamp_reasons: List of reasons if clamped (e.g., ["max_position_pct", "adv_cap"])
        as_of: Point-in-time timestamp of the decision
    """

    instrument: Instrument
    target_weight: float
    target_shares: int
    current_shares: int
    delta_shares: int
    side: Optional[OrderSide]
    reason: str
    signal_contributions: dict[str, float] = None
    risk_gate_clamp: bool = False
    clamp_reasons: tuple[str, ...] = ()
    as_of: datetime = None

    def __post_init__(self):
        if self.signal_contributions is None:
            object.__setattr__(self, "signal_contributions", {})
        if self.as_of is None:
            object.__setattr__(self, "as_of", datetime.utcnow())
        if self.delta_shares == 0:
            object.__setattr__(self, "side", None)
        elif self.delta_shares > 0 and self.side != OrderSide.BUY:
            object.__setattr__(self, "side", OrderSide.BUY)
        elif self.delta_shares < 0 and self.side != OrderSide.SELL:
            object.__setattr__(self, "side", OrderSide.SELL)

    @property
    def is_trade(self) -> bool:
        return self.delta_shares != 0


@dataclass(frozen=True, slots=True)
class Order:
    """
    Order sent to the broker.

    Attributes:
        instrument: Target instrument
        side: BUY or SELL
        quantity: Integer number of shares
        order_type: MARKET or LIMIT
        limit_price: Limit price (required for LIMIT orders)
        time_in_force: "day" | "gtc" | "ioc" | "fok"
        decision_id: Reference to originating Decision (for audit trail)
        placed_at: Timestamp when order was placed
        client_order_id: Unique client-side order ID
    """

    instrument: Instrument
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    time_in_force: str = "day"
    decision_id: Optional[str] = None
    placed_at: datetime = None
    client_order_id: str = ""

    def __post_init__(self):
        if self.placed_at is None:
            object.__setattr__(self, "placed_at", datetime.utcnow())
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price required for LIMIT orders")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError("limit_price must be > 0")


@dataclass(frozen=True, slots=True)
class Fill:
    """
    Execution fill returned by the broker.

    Attributes:
        order: The original order
        filled_quantity: Shares actually filled (may be < order.quantity)
        fill_price: Price at which shares were filled
        fill_time: Timestamp of the fill
        commission: Commission paid (in instrument currency)
        fees: Additional fees (exchange, regulatory, etc.)
        slippage_bps: Realized slippage in basis points
        broker_order_id: Broker's order ID
        broker_fill_id: Broker's fill ID
    """

    order: Order
    filled_quantity: int
    fill_price: float
    fill_time: datetime
    commission: float = 0.0
    fees: float = 0.0
    slippage_bps: float = 0.0
    broker_order_id: str = ""
    broker_fill_id: str = ""

    def __post_init__(self):
        if self.filled_quantity <= 0:
            raise ValueError("filled_quantity must be > 0")
        if self.filled_quantity > self.order.quantity:
            raise ValueError("filled_quantity cannot exceed order.quantity")
        if self.fill_price <= 0:
            raise ValueError("fill_price must be > 0")
        if self.commission < 0 or self.fees < 0:
            raise ValueError("commission and fees must be >= 0")

    @property
    def total_cost(self) -> float:
        """Total execution cost including commission and fees."""
        return self.commission + self.fees

    @property
    def notional(self) -> float:
        """Fill notional value."""
        return self.filled_quantity * self.fill_price