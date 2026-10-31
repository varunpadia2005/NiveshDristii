import json
import hashlib
import sys
import os

# PYTHONPATH must point to the src directory of the tree being tested
# Run from the tree root with: PYTHONPATH=src python tools/compare_backtest.py

import polars as pl
import niveshdristi

from niveshdristi.indicators import compute_all_indicators
from niveshdristi.signals import generate_signal_series
from niveshdristi.backtest import simulate, BacktestConfig

# Load fixture exactly as test does
df = pl.read_parquet("tests/fixtures/prices_reliance_30d.parquet")
df = compute_all_indicators(df)
df = df.filter(pl.col("adx").is_not_null())

prices = {"RELIANCE": df}
signals = {"RELIANCE": generate_signal_series("RELIANCE", df)}

# Exact same config as test
config = BacktestConfig(
    initial_capital=1_000_000,
    max_position_pct=0.10,
    signal_delay_days=1
)

result = simulate(prices, signals, config=config)

# Extract metrics - use exact field names from result
# result.metrics has: CAGR, Volatility, Sharpe, MaxDD, Trades
metrics = result.metrics
total_return = metrics.get("CAGR", 0.0)
trade_count = int(metrics.get("Trades", 0))

# Total cost - sum of costs from trades if available, else 0
total_cost = 0.0
if hasattr(result, "trades") and len(result.trades) > 0:
    # Check if trades have cost column
    if "cost" in result.trades.columns:
        total_cost = float(result.trades["cost"].sum())
    elif "total_cost" in result.trades.columns:
        total_cost = float(result.trades["total_cost"].sum())

# Equity curve MD5
equity_json = result.equity_curve.write_json()
equity_md5 = hashlib.md5(equity_json.encode()).hexdigest()

# Output exactly one line
output = {
    "total_return": total_return,
    "trade_count": trade_count,
    "total_cost": total_cost,
    "equity_curve_md5": equity_md5,
    "niveshdristi_file": niveshdristi.__file__
}
print(json.dumps(output, sort_keys=True))