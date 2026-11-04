"""Relative Rotation Graph (RRG) and Market Regime detection."""
import polars as pl
import numpy as np
from niveshdristi.config import CFG
from niveshdristi.data.contracts import RegimeReport


SECTOR_ETFS = {
    "IT": "NIFTYIT.NS",
    "Bank": "NIFTYBANK.NS",
    "Auto": "NIFTYAUTO.NS",
    "Pharma": "NIFTYPHARMA.NS",
    "FMCG": "NIFTYFMCG.NS",
    "Metal": "NIFTYMETAL.NS",
    "Energy": "NIFTYENERGY.NS",
    "Infra": "NIFTYINFRA.NS",
}

# Working fallback tickers (some NSE sector indices may not be available on yfinance)
SECTOR_ETFS_FALLBACK = {
    "IT": "NIFTYIT.NS",
    "Bank": "NIFTYBANK.NS",
    "Auto": "NIFTYAUTO.NS",
    "Pharma": "NIFTYPHARMA.NS",
    "FMCG": "NIFTYFMCG.NS",
    "Metal": "NIFTYMETAL.NS",
    "Energy": "NIFTYENERGY.NS",
    "Infra": "NIFTYINFRA.NS",
}


async def compute_rrg(
    sector_data: dict[str, pl.DataFrame],
    benchmark: pl.DataFrame
) -> dict[str, str]:
    """Compute RRG quadrants for each sector vs benchmark."""
    lookback = CFG.regimes.rrg.lookback_days

    bench_ret = benchmark["adj_close"].pct_change(lookback).drop_nulls()
    if len(bench_ret) == 0:
        return {s: "Unknown" for s in sector_data}

    last_bench = bench_ret[-1]
    quadrants = {}

    for sector, df in sector_data.items():
        sec_ret = df["adj_close"].pct_change(lookback).drop_nulls()
        if len(sec_ret) == 0:
            quadrants[sector] = "Unknown"
            continue

        last_sec = sec_ret[-1]
        rs_ratio = (last_sec / last_bench) * 100 if last_bench != 0 else 100

        # RS-Momentum: 5-day change in RS-Ratio
        if len(sec_ret) > 5 and len(bench_ret) > 5 and bench_ret[-6] != 0:
            rs_ratio_5d = (sec_ret[-6] / bench_ret[-6]) * 100
        else:
            rs_ratio_5d = 100
        rs_momentum = rs_ratio - rs_ratio_5d + 100

        if rs_ratio > 100 and rs_momentum > 100:
            quad = "Leading"
        elif rs_ratio > 100 and rs_momentum < 100:
            quad = "Weakening"
        elif rs_ratio < 100 and rs_momentum < 100:
            quad = "Lagging"
        else:
            quad = "Improving"
        quadrants[sector] = quad

    return quadrants


def market_regime(nifty: pl.DataFrame, vix: float) -> str:
    """Classify market regime from Nifty returns/vol and VIX."""
    ret_60 = nifty["adj_close"].pct_change(60).drop_nulls()
    vol_20 = nifty["adj_close"].pct_change().rolling_std(20).drop_nulls()

    if len(ret_60) == 0 or len(vol_20) == 0:
        return "unknown"

    ann_vol = vol_20[-1] * (252 ** 0.5)  # annualized

    if ret_60[-1] > 0.10 and ann_vol < 0.20:
        return "bull"
    if ret_60[-1] < -0.10 or vix > 25:
        return "bear"
    return "choppy"


async def get_regime_report(
    nifty_data: pl.DataFrame,
    sector_data: dict[str, pl.DataFrame],
    vix: float = 15.0
) -> RegimeReport:
    """Build complete RegimeReport."""
    quadrants = await compute_rrg(sector_data, nifty_data)
    state = market_regime(nifty_data, vix)

    return RegimeReport(
        market_state=state,
        vix_level=vix,
        sector_quadrants=quadrants,
        state_probs={}
    )