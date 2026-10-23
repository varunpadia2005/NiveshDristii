"""Decision, Order, Fill — portfolio construction and execution primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.config import ConfigDict

from niveshdristi.core.instrument import Instrument


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class Decision(BaseModel):
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    target_weight: float
    target_shares: int
    current_shares: int
    delta_shares: int
    side: OrderSide | None = None
    reason: str = Field(..., min_length=1)
    signal_contributions: dict[str, float] = {}
    risk_gate_clamp: bool = False
    clamp_reasons: tuple[str, ...] = ()
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _derive_side(self) -> Decision:
        if self.delta_shares == 0:
            object.__setattr__(self, "side", None)
        elif self.delta_shares > 0 and self.side != OrderSide.BUY:
            object.__setattr__(self, "side", OrderSide.BUY)
        elif self.delta_shares < 0 and self.side != OrderSide.SELL:
            object.__setattr__(self, "side", OrderSide.SELL)
        return self

    @property
    def is_trade(self) -> bool:
        return self.delta_shares != 0


class Order(BaseModel):
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    side: OrderSide
    quantity: int = Field(..., gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    time_in_force: str = "day"
    decision_id: str | None = None
    placed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    client_order_id: str = ""

    @model_validator(mode="after")
    def _validate_limit_price(self) -> Order:
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price required for LIMIT orders")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError("limit_price must be > 0")
        return self

    @field_validator("quantity")
    @classmethod
    def _quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class Fill(BaseModel):
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: Order
    filled_quantity: int = Field(..., gt=0)
    fill_price: float = Field(..., gt=0)
    fill_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    commission: float = Field(default=0.0, ge=0)
    fees: float = Field(default=0.0, ge=0)
    slippage_bps: float = 0.0
    broker_order_id: str = ""
    broker_fill_id: str = ""

    @model_validator(mode="after")
    def _validate_fill(self) -> Fill:
        if self.filled_quantity > self.order.quantity:
            raise ValueError("filled_quantity cannot exceed order.quantity")
        return self

    @property
    def total_cost(self) -> float:
        """Total execution cost including commission and fees."""
        return self.commission + self.fees

    @property
    def notional(self) -> float:
        """Fill notional value."""
        return self.filled_quantity * self.fill_price
