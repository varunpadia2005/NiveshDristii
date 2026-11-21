"""Display formatting owned by services (NEW, P8-S4).

All money/percent/date strings the UI shows come from HERE — never from
ui/. Grouping and compact units come from the MarketProfile (India:
3-2-2 "12,34,567.89"; lakh/crore compact forms)."""

from __future__ import annotations

from datetime import date
from typing import Any

INDIAN_GROUP = "indian"


def _group_indian(int_part: str) -> str:
    """3-2-2 grouping of a digit string: 1234567 -> 12,34,567."""
    if len(int_part) <= 3:
        return int_part
    head, tail = int_part[:-3], int_part[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def _group_western(int_part: str) -> str:
    """3-3-3 grouping: 1234567 -> 1,234,567."""
    return f"{int(int_part):,}"


def format_money(amount: float, profile: Any) -> str:
    """Grouped digits, 2 decimals, profile grouping. Hand-derived:
    1234567.89 -> 12,34,567.89 (indian); 12345 -> 12,345.00; 999 -> 999.00;
    -1234567.89 -> -12,34,567.89; 0 -> 0.00."""
    neg = amount < 0
    q = f"{abs(amount):.2f}"
    int_part, frac = q.split(".")
    grouped = (
        _group_indian(int_part)
        if profile.digit_grouping == INDIAN_GROUP
        else _group_western(int_part)
    )
    sign = "-" if neg else ""
    return f"{sign}{grouped}.{frac}"


def format_compact(amount: float, profile: Any) -> str:
    """Compact money with the profile's unit labels. Hand-derived (indian):
    25000000 -> 2.50 crore; 250000 -> 2.50 lakh; 1234567.89 -> 12.35 lakh;
    999 -> 999.00 (below the smallest unit)."""
    neg = amount < 0
    value = abs(amount)
    for suffix, divisor in profile.compact_units:
        if value >= divisor:
            return f"{'-' if neg else ''}{value / divisor:.2f} {suffix}"
    return format_money(amount, profile)


def format_pct(fraction: float) -> str:
    """Percent, 1 decimal. Hand-derived: 0.0523 -> 5.2%; 0.0 -> 0.0%;
    -0.031 -> -3.1%; 1.0 -> 100.0%."""
    return f"{fraction * 100:.1f}%"


def format_date(d: date | str) -> str:
    """ISO YYYY-MM-DD (identity for ISO strings)."""
    if isinstance(d, str):
        return d[:10]
    return d.isoformat()


class _Grouping:
    """Minimal profile shim: only digit_grouping is needed."""

    def __init__(self, grouping: str) -> None:
        self.digit_grouping = grouping


def format_money_code(amount: float, currency_code: str = "") -> str:
    """P18-UI-S3a: grouped money string selected by CURRENCY CODE (no
    profile object needed): INR uses the market's 3-2-2 indian grouping,
    every other code uses western grouping. Codes come from MarketRules
    labels; never a symbol literal."""
    grouping = "indian" if currency_code.upper() == "INR" else "western"
    return format_money(amount, _Grouping(grouping))
