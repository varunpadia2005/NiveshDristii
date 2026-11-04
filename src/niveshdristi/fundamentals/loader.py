"""Fundamentals loader: yfinance .info + financials, cached weekly in PostgreSQL."""
import yfinance as yf
from datetime import date, timedelta
from typing import Optional
import asyncpg
from niveshdristi.config import CFG
from niveshdristi.data.contracts import FundamentalData, GuardrailReport


async def _get_pg_pool():
    dsn = CFG.data.cache.pg_dsn
    if not dsn:
        return None
    try:
        return await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=5)
    except Exception:
        return None


FUNDAMENTALS_DDL = """
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker TEXT NOT NULL,
    pe_ratio DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    debt_to_equity DOUBLE PRECISION,
    profit_margin DOUBLE PRECISION,
    revenue_growth DOUBLE PRECISION,
    sector TEXT,
    as_of DATE NOT NULL,
    PRIMARY KEY (ticker, as_of)
);
CREATE INDEX IF NOT EXISTS idx_fund_ticker_asof ON fundamentals (ticker, as_of DESC);
"""


async def init_fundamentals_pg():
    pool = await _get_pg_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(FUNDAMENTALS_DDL)
        except Exception:
            pass


async def get_fundamentals_pg(ticker: str) -> Optional[FundamentalData]:
    pool = await _get_pg_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM fundamentals WHERE ticker = $1 ORDER BY as_of DESC LIMIT 1", ticker
        )
        if row:
            return FundamentalData(**dict(row))
    return None


async def save_fundamentals_pg(data: FundamentalData) -> None:
    pool = await _get_pg_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO fundamentals (ticker, pe_ratio, pb_ratio, roe, debt_to_equity,
                profit_margin, revenue_growth, sector, as_of)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (ticker, as_of) DO UPDATE SET
                pe_ratio = EXCLUDED.pe_ratio,
                pb_ratio = EXCLUDED.pb_ratio,
                roe = EXCLUDED.roe,
                debt_to_equity = EXCLUDED.debt_to_equity,
                profit_margin = EXCLUDED.profit_margin,
                revenue_growth = EXCLUDED.revenue_growth,
                sector = EXCLUDED.sector
        """, data.ticker, data.pe_ratio, data.pb_ratio, data.roe, data.debt_to_equity,
            data.profit_margin, data.revenue_growth, data.sector, data.as_of)


def fetch_yfinance_fundamentals(ticker: str) -> FundamentalData:
    """Fetch from yfinance .info - provides P/E, ROE, D/E, Sector out of box."""
    yf_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
    stock = yf.Ticker(yf_ticker)
    info = stock.info

    # yfinance sometimes gives D/E as percentage (e.g., 150 = 1.5), sometimes ratio
    de = info.get("debtToEquity")
    if de and de > 10:  # Likely percentage
        de = de / 100

    return FundamentalData(
        ticker=ticker,
        pe_ratio=info.get("trailingPE"),
        pb_ratio=info.get("priceToBook"),
        roe=info.get("returnOnEquity"),
        debt_to_equity=de,
        profit_margin=info.get("profitMargins"),
        revenue_growth=info.get("revenueGrowth"),
        sector=info.get("sector", "Unknown"),
        as_of=date.today()
    )


async def load_fundamentals(ticker: str, force_refresh: bool = False) -> FundamentalData:
    """Load fundamentals with weekly PG cache."""
    # Check PG cache first (weekly TTL)
    if not force_refresh:
        cached = await get_fundamentals_pg(ticker)
        if cached and (date.today() - cached.as_of).days < 7:
            return cached

    # Fetch fresh
    data = fetch_yfinance_fundamentals(ticker)
    await save_fundamentals_pg(data)
    return data


def check_guardrails(fund: FundamentalData) -> GuardrailReport:
    """Evaluate guardrail rules from config."""
    flags = []
    for rule in CFG.fundamentals.guardrails:
        val = getattr(fund, rule.metric, None)
        if val is None:
            continue
        op, thresh = rule.operator, rule.threshold
        triggered = (
            (op == ">" and val > thresh) or
            (op == "<" and val < thresh) or
            (op == ">=" and val >= thresh) or
            (op == "<=" and val <= thresh) or
            (op == "==" and val == thresh)
        )
        if triggered:
            flags.append({
                "metric": rule.metric,
                "value": val,
                "severity": rule.severity,
                "message": rule.message
            })

    max_cap = 100
    if any(f["severity"] == "warn" for f in flags):
        max_cap = 60
    elif any(f["severity"] == "error" for f in flags):
        max_cap = 30

    return GuardrailReport(flags=flags, max_score_cap=max_cap)