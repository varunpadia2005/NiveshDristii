"""Price adjustment: splits, dividends, suspicious move detection."""
import polars as pl
from niveshdristi.config import CFG


def adjust_prices(df: pl.DataFrame) -> pl.DataFrame:
    """Apply split/dividend adjustments using adj_close from yfinance.
    Add adj_* columns and adjustment factor. Flag moves > threshold.
    """
    if "adj_close" not in df.columns:
        # No adjustment data available
        return df.with_columns([
            pl.col("close").alias("adj_close"),
            pl.lit(1.0).alias("adj_factor"),
            pl.lit(False).alias("suspicious_move"),
        ])

    # Adjustment factor = adj_close / close
    adj_factor = pl.col("adj_close") / pl.col("close")

    out = df.with_columns([
        (pl.col("open") * adj_factor).alias("adj_open"),
        (pl.col("high") * adj_factor).alias("adj_high"),
        (pl.col("low") * adj_factor).alias("adj_low"),
        (pl.col("close") * adj_factor).alias("adj_close"),
        adj_factor.alias("adj_factor"),
    ])

    # Flag suspicious single-day moves on adjusted close (>40% default)
    daily_pct = out["adj_close"].pct_change().abs()
    threshold = CFG.data.validation.max_daily_move_pct / 100
    out = out.with_columns(
        (daily_pct > threshold).alias("suspicious_move")
    )

    return out