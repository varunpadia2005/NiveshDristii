"""Engine `advance()` — single session step shared by backtest and paper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from niveshdristi.core.decision import Decision, Fill
from niveshdristi.core.session import SessionRecord


@dataclass
class FundState:
    """Current fund state for advance()."""
    cash: float
    positions: dict[str, int]  # symbol -> shares
    session_id: int
    last_session_date: date | None = None


def advance(
    fund_state: FundState,
    session_date: date,
    market_id: str,
    decisions: list[Decision],
    pending_fills: list[Fill],
    data_client: object,  # DataClient protocol (to be defined)
    broker: object,  # Broker protocol (to be defined)
) -> tuple[FundState, SessionRecord]:
    """
    Single session advance — shared by backtest and paper trading.

    Steps (per CHANGES.md C5):
    1. Reconcile: verify broker positions match ledger
    2. Execute: fill pending decisions from previous session (at T+1)
    3. Mark: mark-to-market current positions
    4. Assess: on rebalance days, generate new decisions
    5. Record: create SessionRecord with hash chain

    Args:
        fund_state: Current fund state (cash, positions, session_id)
        session_date: Trading date for this session
        market_id: Market identifier (e.g., "IN_NSE")
        decisions: New decisions from assessment step
        pending_fills: Fills from executing previous session's orders
        data_client: DataClient for price/market data
        broker: Broker for order execution

    Returns:
        Tuple of (updated FundState, new SessionRecord)
    """
    # TODO: Implement per spec
    # This is a stub for Phase 1 structure
    raise NotImplementedError("advance() to be implemented in Phase 5")


def reconcile_positions(
    fund_state: FundState,
    broker_positions: dict[str, int],
    tolerance: int = 0,
) -> bool:
    """Reconcile ledger positions with broker positions."""
    # TODO: Implement
    return True


def mark_to_market(
    fund_state: FundState,
    session_date: date,
    market_id: str,
    data_client: object,
) -> tuple[float, dict[str, float]]:
    """Mark positions to market, return (total_equity, position_values)."""
    # TODO: Implement
    return fund_state.cash, {}
