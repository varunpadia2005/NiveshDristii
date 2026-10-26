"""Fund state and pending decision (NEW, Phase 5).

FundState is a FROZEN dataclass; advance() returns a NEW FundState each
session. Lots are the position truth (FIFO order); positions are derived by
summing lots. All collections are immutable (tuples / MappingProxyType-free
plain tuples — callers get no mutable handle).

The separation between ModelInputs (as_of-limited, models) and
ExecutionPrices (fill session, broker) is BY CONSTRUCTION AND CONVENTION,
not a security boundary: Python cannot prevent a model from closing over
other data; the tests pin the shapes and the builder's DataError.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from niveshdristi.portfolio.risk_gates import GatedTargets


@dataclass(frozen=True, slots=True)
class Lot:
    """One buy lot (FIFO consumption on sells)."""

    symbol: str
    quantity: int  # always positive
    buy_date: date
    cost_per_share: float


@dataclass(frozen=True, slots=True)
class RealizedSale:
    """One FIFO-consumed slice of a sell (for tax accrual)."""

    symbol: str
    quantity: int
    buy_date: date
    sell_date: date
    cost_per_share: float
    sell_price: float

    @property
    def gain(self) -> float:
        return (self.sell_price - self.cost_per_share) * self.quantity


@dataclass(frozen=True, slots=True)
class PendingDecision:
    """Gated targets decided at decision_date, executed NEXT session."""

    decision_date: date
    gated: GatedTargets


@dataclass(frozen=True, slots=True)
class GrossLot:
    """Shadow-track lot: filled at the UNSLIPPED close, no fees."""

    symbol: str
    quantity: int
    cost_per_share: float


@dataclass(frozen=True, slots=True)
class FundState:
    cash: float
    lots: tuple[Lot, ...] = ()
    # Independent GROSS shadow track (R6d): fills at the UNSLIPPED session
    # close with NO fees. Never derived from net.
    gross_cash: float = 0.0
    gross_lots: tuple[GrossLot, ...] = ()
    realized: tuple[RealizedSale, ...] = ()
    tax_accrued: float = 0.0
    pending_decision: PendingDecision | None = None
    session_seq: int = 0
    last_session: date | None = None
    last_hash: str = "0" * 64

    def positions(self) -> dict[str, int]:
        """Derived view: symbol -> total shares across lots."""
        out: dict[str, int] = {}
        for lot in self.lots:
            out[lot.symbol] = out.get(lot.symbol, 0) + lot.quantity
        return out

    def with_(self, **changes: Any) -> FundState:
        """Replace fields (frozen replace helper)."""
        return replace(self, **changes)
