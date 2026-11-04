"""Macro data loaders: VIX, USD/INR, Crude, G-Sec yields."""
import polars as pl
from datetime import date
from typing import Optional
import yfinance as yf
from niveshdristi.data.cache import load_parquet, save_parquet


MACRO_TICKERS = {
    "vix": "^INDIAVIX",      # India VIX
    "usdinr": "INR=X",       # USD/INR
    "crude": "CL=F",         # Crude Oil WTI
    "gs10y": "^TNX",         # 10Y US Treasury (proxy)
}


async def load_macro(series: str, start: Optional[date] = None) -> pl.DataFrame:
    """Load macro series with Parquet caching."""
    if series not in MACRO_TICKERS:
        raise ValueError(f"Unknown macro series: {series}")

    cache_path = f"cache/macro/{series}.parquet"
    import os
    os.makedirs("cache/macro", exist_ok=True)

    # Try cache
    cached = load_parquet(cache_path)
    if cached is not None and len(cached) > 0:
        if start is None or cached["date"].max() >= start:
            return cached

    # Fetch fresh
    ticker = MACRO_TICKERS[series]
    pdf = yf.download(ticker, start=start, progress=False, auto_adjust=False)
    if pdf.empty:
        raise ValueError(f"No data for {series} ({ticker})")

    pdf.columns = [c.lower().replace(" ", "_") for c in pdf.columns]
    df = pl.from_pandas(pdf.reset_index())
    df = df.rename({"date": "date", "adj_close": "value"})
    df = df.select(["date", "value"])

    # Save cache
    df.write_parquet(cache_path)
    return df


async def get_latest_macro() -> dict:
    """Get latest values for all macro series."""
    results = {}
    for series in MACRO_TICKERS:
        try:
            df = await load_macro(series)
            results[series] = {"date": str(df["date"][-1]), "value": float(df["value"][-1])}
        except Exception as e:
            results[series] = {"error": str(e)}
    return results