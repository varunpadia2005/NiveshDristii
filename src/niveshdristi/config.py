"""Configuration loader — env > user config > defaults, with YAML schemas."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import os

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from niveshdristi.core.errors import ConfigurationError


# ============================================================
# Pydantic models for config validation
# ============================================================

class DataConfig(BaseModel):
    provider: str = "yfinance"
    cache_dir: str = "cache/prices"
    pg_dsn: Optional[str] = None
    universe: list[str] = Field(default_factory=list)
    validation_max_daily_move_pct: float = 40.0
    validation_min_trading_days: int = 252
    validation_max_missing_pct: float = 5.0


class IndicatorsConfig(BaseModel):
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    ema_periods: list[int] = Field(default_factory=lambda: [20, 50, 200])


class SignalsConfig(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: {
        "trend": 0.35, "momentum": 0.30, "volatility": 0.15, "volume": 0.20
    })
    score_bounds: list[float] = Field(default_factory=lambda: [-1.0, 1.0])
    normalization: str = "sigmoid"


class GuardrailRule(BaseModel):
    """Guardrail rule for fundamental metrics."""
    metric: str
    operator: str
    threshold: float
    severity: str = "warn"
    message: str = ""
    applies_to: str = "all"


class FundamentalsConfig(BaseModel):
    refresh_cron: str = "0 6 * * 1"
    guardrails: list[GuardrailRule] = Field(default_factory=list)


class RegimesConfig(BaseModel):
    rrg_lookback_days: int = 52
    rrg_benchmark: str = "^NSEI"
    hmm_n_states: int = 3
    hmm_features: list[str] = Field(default_factory=lambda: ["returns", "realized_vol", "vix"])
    hmm_train_window_days: int = 756
    hmm_embargo_days: int = 10


class BacktestConfig(BaseModel):
    costs: dict[str, float] = Field(default_factory=dict)
    timing_signal_delay_days: int = 1
    initial_capital: float = 1_000_000
    risk_free_rate: float = 0.07


class PortfolioConfig(BaseModel):
    max_position_pct: float = 0.10
    max_sector_pct: float = 0.30
    max_positions: int = 20
    min_trade_pct: float = 0.005
    rebalance_frequency: str = "monthly"


class GenAIConfig(BaseModel):
    provider: str = "openrouter"
    model: str = "deepseek/deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 1500
    fallback_template: str = "analyst_note.j2"
    validator_max_retries: int = 1
    validator_tolerance_pct: float = 0.01
    api_key: str = ""  # From env


class AppConfig(BaseModel):
    theme_default: str = "light"
    cache_ttl_seconds: int = 3600
    pages: list[str] = Field(default_factory=list)


class Settings(BaseSettings):
    """Full application settings with env override support."""

    data: DataConfig = Field(default_factory=DataConfig)
    indicators: IndicatorsConfig = Field(default_factory=IndicatorsConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    fundamentals: FundamentalsConfig = Field(default_factory=FundamentalsConfig)
    regimes: RegimesConfig = Field(default_factory=RegimesConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    genai: GenAIConfig = Field(default_factory=GenAIConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @field_validator("genai", mode="before")
    @classmethod
    def _inject_api_key(cls, v):
        if isinstance(v, dict) and os.getenv("OPENROUTER_API_KEY"):
            v = v.copy()
            v["api_key"] = os.getenv("OPENROUTER_API_KEY")
        return v


# ============================================================
# Config loader with precedence: env > user config > defaults
# ============================================================

@dataclass
class ConfigPaths:
    """Resolved paths for config files."""
    user_config: Optional[Path] = None
    mandates_dir: Optional[Path] = None
    universes_dir: Optional[Path] = None
    strategies_dir: Optional[Path] = None


def _find_config_file() -> Optional[Path]:
    """Find config.yaml in standard locations."""
    candidates = [
        Path("config.yaml"),
        Path("config/config.yaml"),
        Path.home() / ".config" / "niveshdristi" / "config.yaml",
        Path("/etc/niveshdristi/config.yaml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _merge_configs(base: dict, override: dict) -> dict:
    """Deep merge two config dicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    user_config_path: Optional[str | Path] = None,
    mandates_dir: Optional[str | Path] = None,
    universes_dir: Optional[str | Path] = None,
    strategies_dir: Optional[str | Path] = None,
) -> Settings:
    """
    Load configuration with precedence:
    1. Environment variables (highest)
    2. User config file (config.yaml)
    3. Defaults (lowest)
    """
    # Start with defaults
    raw = {}

    # Load user config file
    config_path = Path(user_config_path) if user_config_path else _find_config_file()
    if config_path and config_path.exists():
        raw = _load_yaml(config_path)
    else:
        # Default config.yaml in project root
        default_path = Path("config.yaml")
        if default_path.exists():
            raw = _load_yaml(default_path)

    # Merge env overrides (handled by pydantic_settings automatically)
    return Settings(**raw)


# Global config instance (loaded lazily)
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
# This provides the same interface
class _ConfigProxy:
    """Proxy to access config via CFG.attribute style."""
    def __getattr__(self, name: str):
        cfg = get_config()
        if hasattr(cfg, name):
            return getattr(cfg, name)
        raise AttributeError(f"'ConfigProxy' object has no attribute '{name}'")


class _NestedConfigProxy:
    """Proxy for nested config objects (e.g., CFG.fundamentals)."""
    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name: str):
        if hasattr(self._obj, name):
            return getattr(self._obj, name)
        raise AttributeError(f"'{type(self._obj).__name__}' object has no attribute '{name}'")


def _wrap_nested(cfg: Settings) -> dict:
    """Wrap nested config objects for backward compatibility."""
    return {
        "data": _NestedConfigProxy(cfg.data),
        "indicators": _NestedConfigProxy(cfg.indicators),
        "signals": _NestedConfigProxy(cfg.signals),
        "fundamentals": _NestedConfigProxy(cfg.fundamentals),
        "regimes": _NestedConfigProxy(cfg.regimes),
        "backtest": _NestedConfigProxy(cfg.backtest),
        "portfolio": _NestedConfigProxy(cfg.portfolio),
        "models": _NestedConfigProxy(cfg.models) if hasattr(cfg, "models") else None,
        "genai": _NestedConfigProxy(cfg.genai),
        "app": _NestedConfigProxy(cfg.app),
    }


class _ConfigProxy:
    """Proxy to access config via CFG.attribute style."""
    def __getattr__(self, name: str):
        cfg = get_config()
        if hasattr(cfg, name):
            val = getattr(cfg, name)
            # Wrap nested config objects
            if name in _wrap_nested(cfg):
                return _wrap_nested(cfg)[name]
            return val
        raise AttributeError(f"'ConfigProxy' object has no attribute '{name}'")


CFG = _ConfigProxy()


# ============================================================
# Mandate / Universe / Strategy loaders
# ============================================================

@dataclass
class Mandate:
    """Investment mandate — constraints and objectives without tickers."""
    name: str
    description: str
    market_id: str
    max_position_pct: float
    max_sector_pct: float
    max_positions: int
    min_cash_pct: float
    benchmark: str
    risk_free_rate: float
    rebalance_frequency: str
    allowed_sectors: Optional[list[str]] = None
    excluded_sectors: Optional[list[str]] = None
    custom_constraints: dict = Field(default_factory=dict)


@dataclass
class Universe:
    """Stock universe — list of tickers with optional metadata."""
    name: str
    market_id: str
    tickers: list[str]
    description: str = ""
    source: str = "manual"  # "nifty50", "nifty100", "nifty500", "custom"
    last_updated: Optional[str] = None


@dataclass
class Strategy:
    """Strategy specification — models, blending, capital allocation."""
    name: str
    description: str
    market_id: str
    models: list[dict]  # Each: {model_id, weight, params}
    blend_policy: str = "weighted_avg"  # "weighted_avg", "equal_weight", "max_conviction"
    capital_slice: float = 1.0  # Fraction of total capital


def load_mandate(name: str, mandates_dir: Optional[Path] = None) -> Mandate:
    """Load mandate from YAML file."""
    base = mandates_dir or Path("mandates")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Mandate not found: {path}")
    data = _load_yaml(path)
    return Mandate(**data)


def load_universe(name: str, universes_dir: Optional[Path] = None) -> Universe:
    """Load universe from YAML file."""
    base = universes_dir or Path("universes")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Universe not found: {path}")
    data = _load_yaml(path)
    return Universe(**data)


def load_strategy(name: str, strategies_dir: Optional[Path] = None) -> Strategy:
    """Load strategy from YAML file."""
    base = strategies_dir or Path("strategies")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Strategy not found: {path}")
    data = _load_yaml(path)
    return Strategy(**data)