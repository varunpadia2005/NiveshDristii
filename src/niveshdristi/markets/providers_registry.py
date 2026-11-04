"""Provider registry keyed by MARKET ID (NEW, P9-S4).

The spec's registry hook: same DataClient protocol for any country; the
lookup is by market_id. Shells are registered at import time exactly like
the profiles."""

from __future__ import annotations

from typing import Any

_PROVIDER_REGISTRY: dict[str, Any] = {}


def register_provider(market_id: str, client_class: Any) -> None:
    _PROVIDER_REGISTRY[market_id] = client_class


def get_provider_for_market(market_id: str) -> Any:
    """The DataClient CLASS for a market id; KeyError with the available
    ids when unknown (no silent fallback)."""
    if market_id not in _PROVIDER_REGISTRY:
        raise KeyError(
            f"no provider registered for market_id {market_id!r}; "
            f"available: {sorted(_PROVIDER_REGISTRY)}"
        )
    return _PROVIDER_REGISTRY[market_id]


# IN_NSE: the yfinance-backed client (lazy import to avoid module-load I/O
# surface changes; the class itself imports yfinance lazily too).
from niveshdristi.markets.in_nse.providers.yfinance_adapter import (  # noqa: E402
    YFinanceClient,
)
from niveshdristi.markets.in_us.providers.us_adapter import (  # noqa: E402
    UsProviderShell,
)

register_provider("IN_NSE", YFinanceClient)
register_provider("US_NYSE", UsProviderShell)
