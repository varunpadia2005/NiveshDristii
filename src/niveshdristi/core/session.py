"""SessionRecord — immutable record of one trading session for ledger/audit."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from hashlib import sha256

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from niveshdristi.core.decision import Decision, Fill
from niveshdristi.core.instrument import Instrument


class PositionSnapshot(BaseModel):
    """Position state at a point in time."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    shares: int
    avg_cost: float  # Average cost per share (for P&L)
    market_value: float  # Current market value


class SessionRecord(BaseModel):
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: int
    session_date: date
    previous_hash: str
    decisions: tuple[Decision, ...] = ()
    fills: tuple[Fill, ...] = ()
    positions_after: tuple[PositionSnapshot, ...] = ()
    cash_after: float = 0.0
    equity_after: float = 0.0
    risk_metrics: dict[str, float] = {}
    events: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def _to_paise(value: float) -> int:
        """Canonical paise conversion for hash inputs (ROUND_HALF_UP)."""
        from decimal import ROUND_HALF_UP, Decimal

        return int(
            (Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )

    def _canonical(self) -> dict:
        """Amendment B (P6-S1): canonical hash form — ALL money fields as
        integer paise, fixed key order (json sort_keys). Additions only:
        the model fields themselves are unchanged."""
        def money_map(entries):
            out = []
            for item in entries:
                d = dict(item)
                if "fill_price" in d:
                    d["fill_price"] = self._to_paise(d["fill_price"])
                if "commission" in d:
                    d["commission"] = self._to_paise(d["commission"])
                if "fees" in d:
                    d["fees"] = self._to_paise(d["fees"])
                out.append(d)
            return out

        data = {
            "session_id": self.session_id,
            "session_date": self.session_date.isoformat(),
            "previous_hash": self.previous_hash,
            "decisions": [d.model_dump() for d in self.decisions],
            "fills": money_map(f.model_dump() for f in self.fills),
            "positions_after": [
                {**p.model_dump(), "avg_cost": self._to_paise(p.avg_cost),
                 "market_value": self._to_paise(p.market_value)}
                for p in self.positions_after
            ],
            "cash_after": self._to_paise(self.cash_after),
            "equity_after": self._to_paise(self.equity_after),
            "risk_metrics": self.risk_metrics,
            "events": self.events,
            "created_at": self.created_at.isoformat(),
        }
        return data

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this record (excluding the hash itself).

        Amendment B (P6-S1): the hash input is the CANONICAL form — all
        money fields as integer paise, fixed key order — so a live tick, a
        backtest and a replay of the same session hash identically even if
        their float paths differ in the last bits."""
        serialized = json.dumps(self._canonical(), sort_keys=True, default=str)
        return sha256(serialized.encode()).hexdigest()

    def verify_chain(self, previous_record: SessionRecord | None) -> bool:
        """Verify this record correctly links to the previous one."""
        if previous_record is None:
            return self.previous_hash == "0" * 64
        return self.previous_hash == previous_record.compute_hash()

    @classmethod
    def create_genesis_record(
        cls,
        initial_cash: float,
        session_date: date,
        initial_positions: tuple[PositionSnapshot, ...] = (),
    ) -> SessionRecord:
        """Create the genesis (session 0) record."""
        initial_cash + sum(p.market_value for p in initial_positions)
        return cls(
            session_id=0,
            session_date=session_date,
            previous_hash="0" * 64,
            cash_after=initial_cash,
            equity_after=initial_cash + sum(p.market_value for p in initial_positions),
            positions_after=initial_positions,
        )


def create_genesis_record(
    initial_cash: float,
    session_date: date,
    initial_positions: tuple[PositionSnapshot, ...] = (),
) -> SessionRecord:
    """Create the genesis (session 0) record (module-level function for backwards compatibility)."""
    return SessionRecord.create_genesis_record(initial_cash, session_date, initial_positions)
