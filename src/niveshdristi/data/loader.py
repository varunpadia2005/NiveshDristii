"""High-level data loading API."""
import asyncio

from niveshdristi.config import CFG
from niveshdristi.data.cache import init_pg, load_prices
from niveshdristi.data.contracts import PriceData
from niveshdristi.data.providers import get_provider


async def load_universe(tickers: list[str] = None) -> dict[str, PriceData]:
    """Load price data for multiple tickers concurrently."""
    tickers = tickers or CFG.data.universe
    provider = get_provider()

    # Initialize PG on first run
    await init_pg()

    # Fetch all tickers concurrently
    tasks = [load_prices(t, provider=provider) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    data = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            print(f"Failed to load {ticker}: {result}")
        else:
            data[ticker] = result

    return data


def get_ticker_suffix(ticker: str) -> str:
    """Ensure NSE ticker has .NS suffix."""
    if not ticker.endswith(".NS") and not ticker.startswith("^"):
        return f"{ticker}.NS"
    return ticker


async def refresh_all() -> dict[str, str]:
    """Force refresh all universe tickers. Returns status dict."""
    await init_pg()
    provider = get_provider()
    status = {}

    for ticker in CFG.data.universe:
        try:
            await load_prices(ticker, provider=provider, force_refresh=True)
            status[ticker] = "ok"
        except Exception as e:
            status[ticker] = f"error: {e}"

    return status
