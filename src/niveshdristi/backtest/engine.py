"""Honest backtest engine: 1-day delay, full Indian cost model, Polars vectorized."""
import polars as pl
import numpy as np
from typing import Dict, List, Optional
from niveshdristi.config import CFG, BacktestConfig
from niveshdristi.data.contracts import Trade, BacktestResult


def _compute_cost_bps() -> float:
    """Compute all-in cost in bps from config."""
    c = CFG.backtest.costs
    # Round-trip cost (buy + sell)
    buy_cost = (c.brokerage_per_order + c.exchange_charges_pct * 100 +
                c.sebi_fees_pct * 100 + c.stamp_duty_buy_pct * 100 +
                c.slippage_bps)
    sell_cost = (c.brokerage_per_order + c.exchange_charges_pct * 100 +
                 c.sebi_fees_pct * 100 + c.stt_delivery_sell_pct * 100 +
                 c.slippage_bps)
    # Add GST on brokerage + charges
    gst_mult = 1 + c.gst_pct / 100
    return (buy_cost + sell_cost) * gst_mult


def simulate(
    prices: Dict[str, pl.DataFrame],
    signals: Dict[str, pl.Series],  # aligned to price dates
    config: Optional[BacktestConfig] = None
) -> BacktestResult:
    """Vectorized backtest with mandatory 1-day delay: signal@close -> trade@next_open."""
    config = config or BacktestConfig(
        initial_capital=CFG.backtest.initial_capital,
        max_position_pct=CFG.portfolio.max_position_pct,
        signal_delay_days=CFG.backtest.signal_delay_days,
    )

    # Align all dates
    all_dates = pl.concat([df.select("date") for df in prices.values()]).unique().sort("date")
    dates = all_dates["date"].to_list()

    # Prepare lagged signals (signal at t-1 -> trade at t)
    lagged_signals = {}
    for ticker, sig in signals.items():
        # signals aligned to prices[ticker] dates
        sig_df = pl.DataFrame({
            "date": prices[ticker]["date"],
            "signal": sig
        })
        # Shift signal forward by 1 day (next trading day)
        sig_df = sig_df.with_columns(
            pl.col("date").shift(-config.signal_delay_days).alias("trade_date")
        )
        lagged_signals[ticker] = sig_df.filter(pl.col("trade_date").is_not_null())

    cash = config.initial_capital
    positions: Dict[str, int] = {}
    equity = []
    trades = []
    cost_bps = config.costs.total_round_trip_bps()
    cost_mult = 1 + cost_bps / 10000

    for i, dt in enumerate(dates[:-1]):
        next_dt = dates[i + 1]

        # Mark to market
        portfolio_value = cash
        for tkr, shares in positions.items():
            if shares > 0:
                prow = prices[tkr].filter(pl.col("date") == dt)
                if len(prow) > 0:
                    portfolio_value += shares * prow["adj_close"][0]

        equity.append({"date": dt, "equity": portfolio_value})

        # Execute lagged signals from previous day
        if i == 0:
            continue
        prev_dt = dates[i - 1]

        for tkr, sig_df in lagged_signals.items():
            sig_row = sig_df.filter(pl.col("trade_date") == dt)
            if len(sig_row) == 0:
                continue

            signal = sig_row["signal"][0]
            prow = prices[tkr].filter(pl.col("date") == dt)
            if len(prow) == 0:
                continue

            # Trade at next day's open (or close if open not available)
            price = prow["adj_open"][0] if "adj_open" in prow.columns else prow["adj_close"][0]
            current_shares = positions.get(tkr, 0)

            # Simple sizing: max position % per stock
            target_shares = 0
            if signal > 0.2:
                target_shares = int((portfolio_value * config.max_position_pct) / price)
            elif signal < -0.2:
                target_shares = 0

            delta = target_shares - current_shares
            if delta != 0:
                trade_val = abs(delta) * price
                cost_bps = config.costs.total_round_trip_bps()
                cost = trade_val * (cost_bps / 10000)
                cash -= delta * price + cost
                positions[tkr] = target_shares
                trades.append(Trade(
                    date=dt, ticker=tkr,
                    side="buy" if delta > 0 else "sell",
                    price=price, shares=abs(delta), cost=cost
                ))

    eq_df = pl.DataFrame(equity)
    tr_df = pl.DataFrame(trades) if trades else pl.DataFrame(schema={
        "date": pl.Date, "ticker": pl.Utf8, "side": pl.Utf8,
        "price": pl.Float64, "shares": pl.Int64, "cost": pl.Float64
    })

    returns = eq_df["equity"].pct_change().drop_nulls()
    metrics = {
        "CAGR": float((eq_df["equity"][-1] / config.initial_capital) ** (252 / len(returns)) - 1) if len(returns) > 0 else 0,
        "Volatility": float(returns.std() * np.sqrt(252)) if len(returns) > 1 else 0,
        "Sharpe": float((returns.mean() * 252 - CFG.backtest.risk_free_rate) / (returns.std() * np.sqrt(252)))
                 if len(returns) > 1 and returns.std() > 0 else 0,
        "MaxDD": float((eq_df["equity"] / eq_df["equity"].cum_max() - 1).min()),
        "Trades": len(trades),
    }

    return BacktestResult(eq_df, tr_df, metrics)


def run_walk_forward(
    prices: Dict[str, pl.DataFrame],
    signals: Dict[str, pl.Series],
    train_window: int = 252,
    test_window: int = 63,
    step: int = 21
) -> List[BacktestResult]:
    """Walk-forward backtest: expanding window train, rolling test."""
    all_dates = pl.concat([df.select("date") for df in prices.values()]).unique().sort("date")
    dates = all_dates["date"].to_list()

    results = []
    for start_idx in range(0, len(dates) - train_window - test_window, step):
        train_end = dates[start_idx + train_window - 1]
        test_end = dates[start_idx + train_window + test_window - 1]

        # Filter data to test period
        test_prices = {
            t: df.filter((pl.col("date") > train_end) & (pl.col("date") <= test_end))
            for t, df in prices.items()
        }
        test_signals = {
            t: sig.filter((pl.col("date") > train_end) & (pl.col("date") <= test_end))
            for t, sig in signals.items()
        }

        if all(len(df) > 10 for df in test_prices.values()):
            res = simulate(test_prices, test_signals)
            results.append(res)

    return results