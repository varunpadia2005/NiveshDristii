"""Config loader with precedence: env > user config > defaults.

New-code scaffolding (not in Phase 0):
- Loader precedence logic
- Mandate / Universe / Strategy YAML loaders
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import os

import yaml
from pydantic import Field

from niveshdristi.core.errors import ConfigurationError

if TYPE_CHECKING:
    from niveshdristi.config import Settings


# ============================================================
# Config loader helpers
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
) -> "Settings":

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