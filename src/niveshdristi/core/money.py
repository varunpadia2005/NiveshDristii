"""Canonical money conversion (NEW, Phase 6, amendment A).

The ledger and FundState store integer PAISE (1 rupee = 100 paise). The
engine computes in floats; at the END of every advance() the state is
snapped to paise so live ticks, backtests and replays are byte-identical
(float cash carried across sessions would drift from cash rebuilt from the
ledger by up to half a paisa per fill).

to_paise uses decimal.Decimal with ROUND_HALF_UP (per the decimal module
this is ties AWAY FROM ZERO for both signs — deterministic, unlike Python's
round() which uses banker's rounding: round(0.005) == 0, round(-0.005) ==
-0). Everything here is NEW (Phase 6 has no ported maths).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_paise(rupees: float) -> int:
    """Convert a rupee float to integer paise, ties away from zero."""
    paise = Decimal(str(rupees)) * 100
    return int(paise.to_integral_value(rounding=ROUND_HALF_UP))


def from_paise(paise: int) -> float:
    """Convert integer paise back to a rupee float (exact: x / 100)."""
    return paise / 100.0


def snap(rupees: float) -> float:
    """Snap a rupee float to the paise grid (to_paise then from_paise)."""
    return from_paise(to_paise(rupees))
