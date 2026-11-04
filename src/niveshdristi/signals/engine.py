"""Signal Engine: converts raw indicators to standardized -1 to +1 scores."""
import numpy as np
import polars as pl
from typing import Dict, List
from niveshdristi.config import CFG
from niveshdristi.data.contracts import SignalReport


def _score_trend(row: dict) -> float:
    """Momentum-following: positive when price > EMAs, ADX strong."""
    score = 0.0
    if row.get("adj_close", 0) > row.get("ema_20", 0): score += 0.3
    if row.get("adj_close", 0) > row.get("ema_50", 0): score += 0.3
    if row.get("adj_close", 0) > row.get("ema_200", 0): score += 0.4
    if row.get("adx", 0) > 25: score *= 1.2
    return np.clip(score, -1, 1)


def _score_momentum(row: dict) -> float:
    """Momentum-following: RSI, MACD."""
    score = 0.0
    rsi = row.get("rsi", 50)
    if rsi > 60: score += 0.5
    elif rsi < 40: score -= 0.5
    if row.get("macd_hist", 0) > 0: score += 0.5
    return np.clip(score, -1, 1)


def _score_volatility(row: dict) -> float:
    """Contrarian: negative when stretched above upper band."""
    bb_pct = row.get("bb_pct", 0.5)
    if bb_pct > 0.8: return -1.0
    if bb_pct < 0.2: return 1.0
    return (0.5 - bb_pct) * 2


def _score_volume(row: dict) -> float:
    """Confirming: OBV trend + volume ratio."""
    score = 0.0
    if row.get("vol_ratio", 1) > 1.5: score += 0.5
    return np.clip(score, -1, 1)


SCORERS = {
    "trend": _score_trend,
    "momentum": _score_momentum,
    "volatility": _score_volatility,
    "volume": _score_volume,
}


def generate_signal_report(ticker: str, df: pl.DataFrame) -> SignalReport:
    """Generate SignalReport from DataFrame with indicators."""
    latest = df.row(-1, named=True)
    w = CFG.signals.weights

    scores = {name: scorer(latest) for name, scorer in SCORERS.items()}

    composite = (
        w.get("trend", 0.35) * scores["trend"] +
        w.get("momentum", 0.30) * scores["momentum"] +
        w.get("volatility", 0.15) * scores["volatility"] +
        w.get("volume", 0.20) * scores["volume"]
    )

    reasons = []
    if latest.get("adj_close", 0) > latest.get("ema_200", 0):
        reasons.append("Price above 200-day EMA")
    rsi = latest.get("rsi", 50)
    if rsi > 70: reasons.append("RSI overbought (>70)")
    elif rsi < 30: reasons.append("RSI oversold (<30)")
    if latest.get("macd_hist", 0) > 0: reasons.append("MACD histogram positive")
    bb_pct = latest.get("bb_pct", 0.5)
    if bb_pct > 0.8: reasons.append("Near upper Bollinger Band")
    if bb_pct < 0.2: reasons.append("Near lower Bollinger Band")
    if latest.get("vol_ratio", 1) > 1.5: reasons.append("Above-average volume")

    return SignalReport(
        ticker=ticker,
        date=latest["date"],
        trend_score=round(scores["trend"], 3),
        momentum_score=round(scores["momentum"], 3),
        volatility_score=round(scores["volatility"], 3),
        volume_score=round(scores["volume"], 3),
        composite=round(composite, 3),
        components={k: round(v, 3) for k, v in scores.items()},
        reasons=reasons
    )


def generate_signal_series(ticker: str, df: pl.DataFrame) -> pl.Series:
    """Generate signal composite series for backtesting."""
    # Compute scores row by row (vectorized via map_elements)
    def row_score(row):
        scores = {name: scorer(row) for name, scorer in SCORERS.items()}
        w = CFG.signals.weights
        return (
            w.get("trend", 0.35) * scores["trend"] +
            w.get("momentum", 0.30) * scores["momentum"] +
            w.get("volatility", 0.15) * scores["volatility"] +
            w.get("volume", 0.20) * scores["volume"]
        )

    return df.select(pl.struct(pl.all()).map_elements(row_score, return_dtype=pl.Float64)).to_series()