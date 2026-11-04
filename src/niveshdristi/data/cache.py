"""Caching layer: Parquet (local, fast) + PostgreSQL (shared, persistent)."""
import polars as pl
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import asyncpg
from datetime import date

from niveshdristi.data.providers import RawPriceData, DataProvider


@dataclass
class CachedPriceData:
    ticker: str
    df: pl.DataFrame
    metadata: dict


def _get_parquet_dir() -> Path:
    from niveshdristi.config import CFG
    return Path(CFG.data.cache.parquet_dir)


def _ensure_parquet_dir():
    _get_parquet_dir().mkdir(parents=True, exist_ok=True)


def _parquet_path(ticker: str) -> Path:
    _ensure_parquet_dir()
    safe = ticker.replace(".", "_").replace("/", "_")
    return _get_parquet_dir() / f"{safe}.parquet"


def load_parquet(ticker: str) -> Optional[pl.DataFrame]:
    path = _parquet_path(ticker)
    if path.exists():
        return pl.read_parquet(path)
    return None


def save_parquet(ticker: str, df: pl.DataFrame) -> None:
    path = _parquet_path(ticker)
    tmp = path.with_suffix(".tmp")
    df.write_parquet(tmp)
    tmp.replace(path)  # atomic


# --- PostgreSQL Cache ---

async def _get_pg_pool() -> Optional[asyncpg.Pool]:
    from niveshdristi.config import CFG
    dsn = CFG.data.cache.pg_dsn
    if not dsn:
        return None
    try:
        return await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=5)
    except Exception:
        # PG not available, fall back to Parquet only
        return None


PG_INIT_SQL = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    adj_close DOUBLE PRECISION,
    adj_factor DOUBLE PRECISION,
    suspicious_move BOOLEAN,
    source TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices (ticker, date DESC);
"""


async def init_pg() -> None:
    pool = await _get_pg_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(PG_INIT_SQL)
        except Exception:
            # PG not available, continue without it
            pass


async def load_pg(ticker: str, start: Optional[date] = None) -> Optional[pl.DataFrame]:
    pool = await _get_pg_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        query = "SELECT * FROM prices WHERE ticker = $1"
        params = [ticker]
        if start:
            query += " AND date >= $2"
            params.append(start)
        query += " ORDER BY date"
        rows = await conn.fetch(query, *params)
        if rows:
            return pl.DataFrame(rows)
    return None


async def save_pg(ticker: str, df: pl.DataFrame, source: str) -> None:
    pool = await _get_pg_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.executemany("""
            INSERT INTO prices (ticker, date, open, high, low, close, volume, adj_close, adj_factor, suspicious_move, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (ticker, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                adj_close = EXCLUDED.adj_close,
                adj_factor = EXCLUDED.adj_factor,
                suspicious_move = EXCLUDED.suspicious_move,
                source = EXCLUDED.source,
                updated_at = NOW()
        """, [
            (ticker, row["date"], row["open"], row["high"], row["low"], row["close"],
             row["volume"], row["adj_close"], row["adj_factor"], row["suspicious_move"], source)
            for row in df.iter_rows(named=True)
        ])


# --- Unified Loader ---

async def load_prices(
    ticker: str,
    provider: DataProvider = None,
    force_refresh: bool = False,
    use_pg: bool = True
) -> CachedPriceData:
    """Load prices with caching: try Parquet -> PG -> fetch fresh."""
    from niveshdristi.data.providers import get_provider
    from niveshdristi.data.adjust import adjust_prices
    from niveshdristi.data.validate import validate_prices

    provider = provider or get_provider()

    # Try local Parquet first (fastest)
    if not force_refresh:
        cached = load_parquet(ticker)
        if cached is not None and len(cached) > 0:
            return CachedPriceData(ticker, cached, {"cached": True, "source": "parquet"})

    # Try PostgreSQL
    if use_pg and not force_refresh:
        cached = await load_pg(ticker)
        if cached is not None and len(cached) > 0:
            return CachedPriceData(ticker, cached, {"cached": True, "source": "postgres"})

    # Fetch fresh
    raw = provider.fetch(ticker)
    df = adjust_prices(raw.df)
    df = validate_prices(df, ticker)

    # Save to both caches
    save_parquet(ticker, df)
    if use_pg:
        await save_pg(ticker, df, raw.source)

    return CachedPriceData(ticker, df, {"cached": False, "source": raw.source, "fetched_at": raw.fetched_at})