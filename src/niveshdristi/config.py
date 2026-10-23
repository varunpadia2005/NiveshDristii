"""Configuration loader using Pydantic Settings."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml
from pathlib import Path
from dotenv import load_dotenv


# Load .env file first
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class GuardrailRule(BaseSettings):
    metric: str
    operator: str
    threshold: float
    severity: str
    message: str
    applies_to: str = "all"


class CacheConfig(BaseSettings):
    parquet_dir: str = "cache/prices"
    pg_dsn: str = ""
    ttl_days: int = 1


class ValidationConfig(BaseSettings):
    max_daily_move_pct: float = 40.0
    min_trading_days: int = 252
    max_missing_pct: float = 5.0


class DataConfig(BaseSettings):
    provider: str = "yfinance"
    cache: CacheConfig = Field(default_factory=CacheConfig)
    universe: List[str] = Field(default_factory=list)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)


class IndicatorsConfig(BaseSettings):
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    ema_periods: List[int] = Field(default_factory=lambda: [20, 50, 200])


class SignalsConfig(BaseSettings):
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "trend": 0.35, "momentum": 0.30, "volatility": 0.15, "volume": 0.20
    })
    score_bounds: List[float] = Field(default_factory=lambda: [-1.0, 1.0])
    normalization: str = "sigmoid"


class FundamentalsConfig(BaseSettings):
    refresh_cron: str = "0 6 * * 1"
    guardrails: List[GuardrailRule] = Field(default_factory=list)


class RRGConfig(BaseSettings):
    lookback_days: int = 52
    benchmark: str = "^NSEI"


class HMMConfig(BaseSettings):
    n_states: int = 3
    features: List[str] = Field(default_factory=lambda: ["returns", "realized_vol", "vix"])
    train_window_days: int = 756
    embargo_days: int = 10


class RegimesConfig(BaseSettings):
    rrg: RRGConfig = Field(default_factory=RRGConfig)
    hmm: HMMConfig = Field(default_factory=HMMConfig)


class BacktestConfig(BaseSettings):
    costs: Dict[str, float] = Field(default_factory=dict)
    timing: Dict[str, int] = Field(default_factory=dict)
    initial_capital: float = 1_000_000
    risk_free_rate: float = 0.07


class PortfolioConfig(BaseSettings):
    max_position_pct: float = 0.10
    max_sector_pct: float = 0.30
    max_positions: int = 20
    min_trade_pct: float = 0.005
    rebalance_frequency: str = "monthly"


class ModelsConfig(BaseSettings):
    features: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, Any] = Field(default_factory=dict)
    cv: Dict[str, Any] = Field(default_factory=dict)
    lightgbm: Dict[str, Any] = Field(default_factory=dict)


class GenAIConfig(BaseSettings):
    provider: str = "openrouter"
    model: str = "deepseek/deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 1500
    fallback_template: str = "analyst_note.j2"
    validator: Dict[str, Any] = Field(default_factory=dict)
    api_key: str = Field(default="", exclude=True)  # From OPENROUTER_API_KEY env var


class AppConfig(BaseSettings):
    theme_default: str = "light"
    cache_ttl_seconds: int = 3600
    pages: List[str] = Field(default_factory=list)


class Settings(BaseSettings):
    data: DataConfig = Field(default_factory=DataConfig)
    indicators: IndicatorsConfig = Field(default_factory=IndicatorsConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    fundamentals: FundamentalsConfig = Field(default_factory=FundamentalsConfig)
    regimes: RegimesConfig = Field(default_factory=RegimesConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    genai: GenAIConfig = Field(default_factory=GenAIConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",  # Ignore extra env vars like DATABASE_URL, OPENROUTER_API_KEY
    )


def load_config(path: str = "config.yaml") -> Settings:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    
    # Merge with env overrides for specific keys
    import os
    env_overrides = {}
    
    # Handle flat env vars that map to nested config
    if os.getenv("DATABASE_URL"):
        env_overrides.setdefault("data", {}).setdefault("cache", {})["pg_dsn"] = os.getenv("DATABASE_URL")
    if os.getenv("POSTGRES_PASSWORD"):
        # Not directly mapped, but could be used to construct pg_dsn
        pass
    if os.getenv("OPENROUTER_API_KEY"):
        env_overrides.setdefault("genai", {})["api_key"] = os.getenv("OPENROUTER_API_KEY")
    
    # Merge env overrides into raw config
    for key, value in env_overrides.items():
        if key in raw and isinstance(raw[key], dict) and isinstance(value, dict):
            raw[key].update(value)
        else:
            raw[key] = value
    
    return Settings(**raw)


# Global config instance (lazy, typed Settings - not a proxy)
_CFG: Optional[Settings] = None


def get_config() -> Settings:
    """Get global config instance (loads on first call)."""
    global _CFG
    if _CFG is None:
        _CFG = load_config()
    return _CFG


def reset_config() -> None:
    """Reset global config (useful for testing)."""
    global _CFG
    _CFG = None


# Backward compatibility: old code uses `from niveshdristi.config import CFG`
# CFG is the Settings instance directly (properly typed, like Phase 0)
CFG = get_config()