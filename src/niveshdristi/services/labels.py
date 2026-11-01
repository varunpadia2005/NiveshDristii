"""Market labels via the profile (NEW, P8-S1) — NO hard-coded currency
symbols in services/ or ui/; labels come from the MarketProfile."""

from __future__ import annotations

from typing import Any


def market_labels(profile: Any = None) -> dict[str, str]:
    """Neutral label dict from a MarketProfile (default: IN_NSE)."""
    if profile is None:
        from niveshdristi.markets import IN_NSE_PROFILE

        profile = IN_NSE_PROFILE
    return {
        "market_id": profile.market_id,
        "market_name": profile.name,
        "currency_code": profile.currency,  # ISO code, never a symbol
        "timezone": profile.timezone,
    }
