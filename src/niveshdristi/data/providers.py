"""DataProvider protocol - abstract interface for price data sources.
Swap implementations (yfinance, jugaad-data, NSE API, Kite, Upstox, AngelOne) without rewriting downstream code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional, List
import polars as pl
import pandas as pd

from niveshdristi.config import CFG


@dataclass
class RawPriceData:
    ticker: str
    df: pl.DataFrame
    source: str
    fetched_at: date


class DataProvider(ABC):
    """Abstract interface for price data sources."""

    @abstractmethod
    def fetch(self, ticker: str, start: Optional[date] = None, end: Optional[date] = None) -> RawPriceData:
        """Fetch raw OHLCV data for a ticker."""
        pass

    @abstractmethod
    def fetch_batch(self, tickers: List[str], start: Optional[date] = None) -> dict[str, RawPriceData]:
        """Fetch multiple tickers efficiently."""
        pass

    @abstractmethod
    def get_universe(self, name: str) -> List[str]:
        """Return tickers for a named universe (nifty50, nifty500, etc.)."""
        pass


class YFinanceProvider(DataProvider):
    """Yahoo Finance via yfinance library - free, reliable for NSE."""

    def fetch(self, ticker: str, start: Optional[date] = None, end: Optional[date] = None) -> RawPriceData:
        import yfinance as yf
        import pandas as pd
        # Don't add .NS suffix for index tickers (starting with ^)
        yf_ticker = ticker if ticker.endswith(".NS") or ticker.startswith("^") else f"{ticker}.NS"
        
        # Default to 2 years of data if no start/end specified
        if start is None:
            start = date.today().replace(year=date.today().year - 2)
        if end is None:
            end = date.today()
            
        result = yf.download(yf_ticker, start=start, end=end, progress=False, auto_adjust=False)
        # Handle both old (DataFrame) and new (tuple) return formats
        if isinstance(result, tuple):
            pdf = result[0]
        else:
            pdf = result
        if pdf is None or (hasattr(pdf, 'empty') and pdf.empty):
            raise ValueError(f"No data for {ticker}")
        
        # Flatten MultiIndex columns (e.g., ('Adj Close', 'RELIANCE.NS') -> 'adj_close')
        if isinstance(pdf.columns, pd.MultiIndex):
            pdf.columns = [c[0].lower().replace(" ", "_") for c in pdf.columns]
        else:
            pdf.columns = [c.lower().replace(" ", "_") for c in pdf.columns]
        
        # Reset index and ensure all column names are lowercase
        pdf = pdf.reset_index()
        pdf.columns = [c.lower() for c in pdf.columns]
        
        df = pl.from_pandas(pdf)
        return RawPriceData(ticker=ticker, df=df, source="yfinance", fetched_at=date.today())

    def fetch_batch(self, tickers: List[str], start: Optional[date] = None) -> dict[str, RawPriceData]:
        from concurrent.futures import ThreadPoolExecutor
        results = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(self.fetch, t, start): t for t in tickers}
            for fut in futures:
                t = futures[fut]
                try:
                    results[t] = fut.result()
                except Exception as e:
                    print(f"Failed {t}: {e}")
        return results

    def get_universe(self, name: str) -> List[str]:
        return CFG.data.universe if name in ["nifty50", "nifty10", "default"] else []


# Registry for easy swapping
PROVIDERS: dict[str, type[DataProvider]] = {
    "yfinance": YFinanceProvider,
    # "jugaad": JugaadProvider,
    # "nse": NSEProvider,
    # "kite": KiteProvider,
    # "upstox": UpstoxProvider,
    # "angelone": AngelOneProvider,
}


def get_provider(name: str = None) -> DataProvider:
    name = name or CFG.data.provider
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]()