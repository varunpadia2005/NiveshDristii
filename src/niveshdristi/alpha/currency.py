"""Market currency lookup (NEW, P9-S1).

Alpha models must stamp Instrument.currency from the CONTEXT, never as a
hard-coded per-model literal. Alpha CANNOT import the markets layer (the
neutral-package boundary test forbids it), so the mapping lives here and a
TEST asserts it agrees with the markets registry (drift-proof). Unknown or
test market ids fall back to the neutral placeholder "XXX" so existing
tests stay unchanged."""

from __future__ import annotations

# VERIFY: kept in sync with the MarketProfile.currency fields; the test
# test_currency_table_matches_registry asserts agreement.
MARKET_CURRENCIES: dict[str, str] = {
    "IN_NSE": "INR",
    "US_NYSE": "USD",
}

PLACEHOLDER_CURRENCY = "XXX"  # neutral placeholder (unknown/test markets)


def currency_for_market(market_id: str) -> str:
    """Currency for a market id; neutral placeholder otherwise."""
    if not market_id:
        return PLACEHOLDER_CURRENCY
    return MARKET_CURRENCIES.get(market_id, PLACEHOLDER_CURRENCY)
