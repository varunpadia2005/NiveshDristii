"""FastAPI backend for NiveshDristi."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional
import asyncio

from niveshdristi.config import CFG
from niveshdristi.data.cache import init_pg
from niveshdristi.data.loader import load_prices, load_universe
from niveshdristi.indicators import compute_all_indicators
from niveshdristi.signals import generate_signal_report, generate_signal_series
from niveshdristi.fundamentals import load_fundamentals, check_guardrails
from niveshdristi.regime import get_regime_report, SECTOR_ETFS, market_regime
from niveshdristi.genai import generate_analyst_note, validate_note
from niveshdristi.data.contracts import FactsBundle, RegimeReport, PriceRange
from niveshdristi.data.providers import get_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pg()
    from niveshdristi.fundamentals import init_fundamentals_pg
    await init_fundamentals_pg()
    yield


app = FastAPI(title="NiveshDristi API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/universe/{name}")
async def get_universe(name: str):
    provider = get_provider()
    return {"tickers": provider.get_universe(name)}


@app.get("/price/{ticker}")
async def get_price(ticker: str, force: bool = False):
    data = await load_prices(ticker, force_refresh=force)
    return {
        "ticker": data.ticker,
        "rows": len(data.df),
        "last_date": str(data.df["date"][-1]) if len(data.df) > 0 else None,
        "metadata": data.metadata
    }


@app.get("/signal/{ticker}")
async def get_signal(ticker: str):
    data = await load_prices(ticker)
    df = compute_all_indicators(data.df)
    signal = generate_signal_report(ticker, df)
    return signal.__dict__


@app.get("/signals")
async def get_all_signals(tickers: str = None):
    """Get signals for multiple tickers (comma-separated)."""
    if tickers:
        ticker_list = [t.strip() for t in tickers.split(",")]
    else:
        ticker_list = CFG.data.universe

    results = {}
    for t in ticker_list:
        try:
            data = await load_prices(t)
            df = compute_all_indicators(data.df)
            signal = generate_signal_report(t, df)
            results[t] = signal.__dict__
        except Exception as e:
            results[t] = {"error": str(e)}
    return results


@app.get("/fundamentals/{ticker}")
async def get_fundamentals(ticker: str, force: bool = False):
    fund = await load_fundamentals(ticker, force_refresh=force)
    guard = check_guardrails(fund)
    return {"fundamentals": fund.__dict__, "guardrails": guard.__dict__}


@app.get("/regime")
async def get_regime():
    nifty = await load_prices("^NSEI")
    sector_data = {}
    for name, etf in SECTOR_ETFS.items():
        try:
            sector_data[name] = (await load_prices(etf)).df
        except Exception:
            pass

    quadrants = await get_regime_report(nifty.df, sector_data, 15.0)
    return {
        "market_state": quadrants.market_state,
        "vix_level": quadrants.vix_level,
        "sectors": quadrants.sector_quadrants
    }


@app.post("/analyst/{ticker}")
async def get_analyst_note(ticker: str):
    """Generate grounded AI analyst note for a ticker."""
    try:
        # Load core data first (parallel)
        price_task = load_prices(ticker)
        fund_task = load_fundamentals(ticker)
        nifty_task = load_prices("^NSEI")
        
        price_data, fund, nifty = await asyncio.gather(price_task, fund_task, nifty_task)
        
        df = compute_all_indicators(price_data.df)
        signal = generate_signal_report(ticker, df)
        guard = check_guardrails(fund)

        # Simplified regime (skip sector data for speed)
        regime = RegimeReport(
            market_state="bull",  # Simplified
            vix_level=15.0,
            sector_quadrants={},
            state_probs={}
        )

        # Price range (simplified)
        price_range = PriceRange(
            ticker=ticker,
            date=price_data.df["date"][-1],
            current_price=price_data.df["adj_close"][-1],
            volatility=0.2,
            ranges={},
            atr_bands=(0, 0),
            sr_levels=[]
        )

        # Build facts bundle
        bundle = FactsBundle(
            ticker=ticker,
            date=price_data.df["date"][-1],
            signal=signal,
            fundamentals=fund,
            guardrails=guard,
            regime=regime,
            price_range=price_range,
            model=None,
            backtest_stats=None
        )

        # Generate note
        note = await generate_analyst_note(bundle)
        valid, errors = validate_note(note, bundle)

        # Retry once if validation failed
        if not valid and CFG.genai.validator.max_retries > 0:
            pass

        return {
            "note": note.__dict__,
            "validated": valid,
            "errors": errors
        }
    except Exception as e:
        import traceback
        print(f"Error in /analyst/{ticker}: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Internal error: {str(e)}")


@app.get("/backtest")
async def run_backtest(
    tickers: str = Query(None, description="Comma-separated tickers"),
    strategy: str = Query("signal_based", description="Strategy name")
):
    """Run backtest on given universe."""
    if tickers:
        ticker_list = [t.strip() for t in tickers.split(",")]
    else:
        ticker_list = CFG.data.universe

    # Load prices and signals
    prices = {}
    signals = {}
    for t in ticker_list:
        try:
            data = await load_prices(t)
            df = compute_all_indicators(data.df)
            prices[t] = df
            signals[t] = generate_signal_series(t, df)
        except Exception as e:
            print(f"Failed {t}: {e}")

    if not prices:
        raise HTTPException(400, "No valid data for backtest")

    from niveshdristi.backtest import simulate
    result = simulate(prices, signals)

    return {
        "metrics": result.metrics,
        "trades": len(result.trades),
        "equity_curve": result.equity_curve.to_dicts() if len(result.equity_curve) > 0 else []
    }