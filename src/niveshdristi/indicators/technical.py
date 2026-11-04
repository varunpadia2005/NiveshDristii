"""Technical indicators as Polars expressions - vectorized, composable, no loops."""
import polars as pl
from niveshdristi.config import CFG


def sma(period: int) -> pl.Expr:
    return pl.col("adj_close").rolling_mean(window_size=period, min_samples=period)


def ema(period: int) -> pl.Expr:
    return pl.col("adj_close").ewm_mean(span=period, adjust=False)


def rsi(period: int = 14) -> pl.Expr:
    delta = pl.col("adj_close").diff()
    gain = delta.clip(lower_bound=0).rolling_mean(window_size=period, min_samples=period)
    loss = (-delta).clip(lower_bound=0).rolling_mean(window_size=period, min_samples=period)
    rs = gain / loss.replace(0, None)
    return (100 - (100 / (1 + rs))).fill_null(50)


def macd(fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(fast)
    ema_slow = ema(slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm_mean(span=signal, adjust=False)
    hist = macd_line - signal_line
    return {
        "macd": macd_line.alias("macd"),
        "macd_signal": signal_line.alias("macd_signal"),
        "macd_hist": hist.alias("macd_hist"),
    }


def bollinger(period: int = 20, std: float = 2.0):
    mid = sma(period)
    std_dev = pl.col("adj_close").rolling_std(window_size=period, min_samples=period)
    return {
        "bb_upper": (mid + std * std_dev).alias("bb_upper"),
        "bb_mid": mid.alias("bb_mid"),
        "bb_lower": (mid - std * std_dev).alias("bb_lower"),
    }


def atr(period: int = 14) -> pl.Expr:
    tr1 = pl.col("adj_high") - pl.col("adj_low")
    tr2 = (pl.col("adj_high") - pl.col("adj_close").shift(1)).abs()
    tr3 = (pl.col("adj_low") - pl.col("adj_close").shift(1)).abs()
    tr = pl.max_horizontal(tr1, tr2, tr3)
    return tr.rolling_mean(window_size=period, min_samples=period).alias("atr")


def adx(period: int = 14) -> pl.Expr:
    plus_dm = (pl.col("adj_high") - pl.col("adj_high").shift(1)).clip(lower_bound=0)
    minus_dm = (pl.col("adj_low").shift(1) - pl.col("adj_low")).clip(lower_bound=0)

    tr1 = pl.col("adj_high") - pl.col("adj_low")
    tr2 = (pl.col("adj_high") - pl.col("adj_close").shift(1)).abs()
    tr3 = (pl.col("adj_low") - pl.col("adj_close").shift(1)).abs()
    tr = pl.max_horizontal(tr1, tr2, tr3)

    atr_val = tr.rolling_mean(window_size=period, min_samples=period)
    plus_di = 100 * (plus_dm.rolling_mean(window_size=period, min_samples=period) / atr_val)
    minus_di = 100 * (minus_dm.rolling_mean(window_size=period, min_samples=period) / atr_val)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, None)
    return dx.rolling_mean(window_size=period, min_samples=period).alias("adx")


def obv() -> pl.Expr:
    return (pl.when(pl.col("adj_close") > pl.col("adj_close").shift(1))
            .then(pl.col("volume"))
            .when(pl.col("adj_close") < pl.col("adj_close").shift(1))
            .then(-pl.col("volume"))
            .otherwise(0)
           ).cum_sum().alias("obv")


def compute_all_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """Add all indicator columns to price DataFrame."""
    c = CFG.indicators
    exprs = []

    # Trend EMAs
    for p in c.ema_periods:
        exprs.append(ema(p).alias(f"ema_{p}"))
    exprs.append(adx(14))

    # Momentum
    exprs.append(rsi(c.rsi_period).alias("rsi"))
    for k, v in macd(c.macd_fast, c.macd_slow, c.macd_signal).items():
        exprs.append(v)

    # Volatility
    exprs.append(atr(c.atr_period))
    for k, v in bollinger(c.bb_period, c.bb_std).items():
        exprs.append(v)

    # First pass: add all indicators except BB %B
    df = df.with_columns(exprs)

    # Second pass: BB %B (needs bb_upper/bb_lower from first pass)
    df = df.with_columns(
        ((pl.col("adj_close") - pl.col("bb_lower")) /
         (pl.col("bb_upper") - pl.col("bb_lower")).replace(0, None)
        ).alias("bb_pct")
    )

    # Volume
    df = df.with_columns(
        obv(),
        (pl.col("volume") / pl.col("volume").rolling_mean(window_size=20, min_samples=20)
        ).alias("vol_ratio")
    )

    return df


# Registry for dynamic loading
INDICATOR_REGISTRY = {
    "sma": lambda p: sma(p).alias(f"sma_{p}"),
    "ema": lambda p: ema(p).alias(f"ema_{p}"),
    "rsi": lambda p=14: rsi(p).alias("rsi"),
    "macd": lambda f=12, s=26, sig=9: [v for v in macd(f, s, sig).values()],
    "bollinger": lambda p=20, s=2.0: [v for v in bollinger(p, s).values()],
    "atr": lambda p=14: atr(p),
    "adx": lambda p=14: adx(p),
    "obv": lambda: obv(),
}