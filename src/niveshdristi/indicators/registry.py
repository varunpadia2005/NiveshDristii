"""Indicator registry for dynamic loading from config."""
from typing import Callable, Dict, List
import polars as pl
from niveshdristi.indicators.technical import INDICATOR_REGISTRY, compute_all_indicators


def get_indicator_expr(name: str, **params) -> List[pl.Expr]:
    """Get Polars expressions for an indicator by name."""
    if name not in INDICATOR_REGISTRY:
        raise ValueError(f"Unknown indicator: {name}. Available: {list(INDICATOR_REGISTRY.keys())}")
    fn = INDICATOR_REGISTRY[name]
    result = fn(**params)
    return result if isinstance(result, list) else [result]


def compute_indicators_from_config(df: pl.DataFrame, config: dict = None) -> pl.DataFrame:
    """Compute indicators specified in config."""
    if config is None:
        from niveshdristi.config import CFG
        config = {"indicators": ["sma", "ema", "rsi", "macd", "bollinger", "atr", "adx", "obv"]}

    exprs = []
    for ind_config in config.get("indicators", []):
        if isinstance(ind_config, str):
            name, params = ind_config, {}
        else:
            name, params = ind_config.get("name"), ind_config.get("params", {})
        exprs.extend(get_indicator_expr(name, **params))

    return df.with_columns(exprs)