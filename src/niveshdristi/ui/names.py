r"""P18-UI-S2: display-name resolver (symbol -> honest display name).

Rules (R3 — no invented data):
- synthetic demo tickers (SYN\d+) render as "Synthetic Co NNN (demo)" —
  an honest label, never a real company name;
- universe/config names would be used when present — but the tracked
  universes carry bare ticker strings and their schema does not accept a
  per-ticker name field (config_loader validation), so real tickers
  display as the ticker itself until a user-supplied name source exists;
- nothing is typed from memory: no lookup tables of company names here.
"""

from __future__ import annotations

import re

_SYN = re.compile(r"^SYN(\d+)$")


def display_name(symbol: str, *, market_tag: str = "") -> str:
    """Honest display name for a symbol.

    SYN090 -> "Synthetic Co 090 (demo)"; anything else -> the symbol
    itself (never an invented name). market_tag is ignored for real
    tickers and kept for symmetry with future user-supplied sources.
    """
    s = (symbol or "").strip()
    m = _SYN.match(s)
    if m:
        return f"Synthetic Co {int(m.group(1)):03d} (demo)"
    return s


def display_tag(symbol: str) -> str:
    """The visible 'synthetic demo data' tag for synthetic tickers; empty
    string otherwise (so callers can skip the tag line)."""
    return "synthetic demo data" if _SYN.match((symbol or "").strip()) else ""
