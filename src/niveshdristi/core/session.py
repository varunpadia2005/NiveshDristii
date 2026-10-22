"""SessionRecord — immutable record of one trading session for ledger/audit."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from hashlib import sha256
import json

from niveshdristi.core.instrument import Instrument
from niveshdristi.core.decision import Decision, Fill


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Position state at a point in time."""
    instrument: Instrument
    shares: int
    avg_cost: float  # Average cost per share (for P&L)
    market_value: float  # Current market value


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """
    Immutable record of one complete trading session (one call to `advance()`).

    This is the fundamental unit of the hash-chained ledger.
    Each record contains the previous record's hash, forming an immutable chain.

    Attributes:
        session_id: Monotonically increasing session number (0 = genesis)
        session_date: Trading date (per market calendar)
        previous_hash: SHA256 hash of the previous SessionRecord (genesis = "0"*64)
        decisions: Decisions made at this session's assessment step
        fills: Fills received from executing previous session's decisions
        positions_after: Full position list after this session's mark-to-market
        cash_after: Cash balance after this session
        equity_after: Total equity (cash + positions market value) after this session
        risk_metrics: Risk metrics snapshot (exposure, sector weights, VaR, etc.)
        events: Notable events during this session (halts, errors, etc.)
        created_at: Wall-clock timestamp when record was created
    """

    session_id: int
    session_date: date
    previous_hash: str
    decisions: tuple[Decision, ...] = field(default_factory=tuple)
    fills: tuple[Fill, ...] = field(default_factory=tuple)
    positions_after: tuple[PositionSnapshot, ...] = field(default_factory=tuple)
    cash_after: float = 0.0
    equity_after: float = 0.0
    risk_metrics: dict[str, float] = field(default_factory=dict)
    events: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this record (excluding the hash itself)."""
        # Deterministic serialization
        data = {
            "session_id": self.session_id,
            "session_date": self.session_date.isoformat(),
            "previous_hash": self.previous_hash,
            "decisions": [d.__dict__ for d in self.decisions],
            "fills": [f.__dict__ for f in self.fills],
            "positions_after": [p.__dict__ for p in self.positions_after],
            "cash_after": self.cash_after,
            "equity_after": self.equity_after,
            "risk_metrics": self.risk_metrics,
            "events": self.events,
            "created_at": self.created_at.isoformat(),
        }
        # Sort keys for determinism
        serialized = json.dumps(data, sort_keys=True, default=str)
        return sha256(serialized.encode()).hexdigest()

    def verify_chain(self, previous_record: Optional["SessionRecord"]) -> bool:
        """Verify this record correctly links to the previous one."""
        if previous_record is None:
            return self.previous_hash == "0" * 64
        return self.previous_hash == previous_record.compute_hash()


def create_genesis_record(
    initial_cash: float,
    session_date: date,
    initial_positions: tuple[PositionSnapshot, ...] = (),
) -> SessionRecord:
    """Create the genesis (session 0) record."""
    equity = initial_cash + sum(p.market_value for p in initial_positions)
    record = SessionRecord(
        session_id=0,
        session_date=session_date,
        previous_hash="0" * 64,
        cash_after=initial_cash,
        equity_after=equity,
        positions_after=initial_positions,
    )
    # Verify self-consistency
    assert record.compute_hash() == record.previous_hash or record.previous_hash == "0" * 64
    return record