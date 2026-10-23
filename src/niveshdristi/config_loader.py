"""Config loader with precedence: env > user config > defaults.

New-code scaffolding (not in Phase 0):
- Loader precedence logic
- Mandate / Universe / Strategy YAML loaders
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING, get_args
import os
import yaml
from pydantic import Field, field_validator
from pydantic.config import ConfigDict

from niveshdristi.core.errors import ConfigurationError

if TYPE_CHECKING:
    from niveshdristi.config import Settings


# ============================================================
# Config loader helpers
# ============================================================

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
    with open(path, encoding="utf-8") as f:
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


def load_layered_config(
    user_config_path: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None,
    defaults_path: Optional[str | Path] = None,
) -> dict:
    """
    Load configuration with precedence:
    1. Environment variables (highest)
    2. User config file (config.yaml)
    3. Packaged defaults (lowest)

    Args:
        user_config_path: Optional path to user config.yaml
        env: Optional environment variables dict (defaults to os.environ)
        defaults_path: Optional path to defaults config.yaml

    Returns:
        Merged configuration dict ready for Settings(**config)
    """
    env = env or os.environ

    # Layer 1: Defaults (lowest precedence)
    raw = {}

    # Layer 2: Packaged defaults
    defaults_path = Path(defaults_path) if defaults_path else Path("config.yaml")
    if defaults_path.exists():
        with open(defaults_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    # Layer 3: User config file
    config_path = None
    if user_config_path:
        config_path = Path(user_config_path)
    else:
        config_path = _find_config_file()

    if config_path and config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        raw = _merge_configs(raw, user_config)

    # Layer 4: Environment overrides (highest)
    # Handled by pydantic_settings automatically via Settings model_config
    # But we also apply flat env vars here for backward compatibility
    if "DATABASE_URL" in env:
        raw.setdefault("data", {}).setdefault("cache", {})["pg_dsn"] = env["DATABASE_URL"]
    if "OPENROUTER_API_KEY" in env:
        raw.setdefault("genai", {})["api_key"] = env["OPENROUTER_API_KEY"]

    return raw


def load_config(
    user_config_path: Optional[str | Path] = None,
    mandates_dir: Optional[str | Path] = None,
    universes_dir: Optional[str | Path] = None,
    strategies_dir: Optional[str | Path] = None,
) -> "Settings":
    """
    Load configuration with precedence:
    1. Environment variables (highest)
    2. User config file (config.yaml)
    3. Defaults (lowest)
    """
    raw = load_layered_config(user_config_path=user_config_path)
    from niveshdristi.config import Settings
    return Settings(**raw)


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


def _merge_configs(base: dict, override: dict) -> dict:
    """Deep merge two config dicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _validate_no_unknown_keys(data: dict, allowed_keys: set[str], context: str) -> None:
    """Raise ConfigurationError if data contains keys not in allowed_keys."""
    unknown = set(data.keys()) - allowed_keys
    if unknown:
        raise ConfigurationError(f"{context}: unknown keys: {sorted(unknown)}")


# ============================================================
# Mandate / Universe / Strategy loaders
# ============================================================

_REBALANCE_FREQUENCIES = frozenset({"daily", "weekly", "monthly", "quarterly", "annual"})


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

    def __post_init__(self):
        if self.rebalance_frequency not in _REBALANCE_FREQUENCIES:
            raise ValueError(
                f"rebalance_frequency must be one of {sorted(_REBALANCE_FREQUENCIES)}, "
                f"got {self.rebalance_frequency!r}"
            )


@dataclass
class Universe:
    """Stock universe — list of tickers with optional metadata."""
    name: str
    market_id: str
    tickers: list[str]
    description: str = ""
    source: str = "manual"  # "nifty50", "nifty100", "nifty500", "custom"
    last_updated: Optional[str] = None
    as_of: Optional[str] = None
    approximate: bool = False


@dataclass
class Strategy:
    """Strategy specification — models, blending, capital allocation."""
    name: str
    description: str
    market_id: str
    models: list[dict]  # Each: {model_id, weight, params}
    blend_policy: str = "weighted_avg"  # "weighted_avg", "equal_weight", "max_conviction"
    capital_slice: float = 1.0  # Fraction of total capital
    rebalance_frequency: str = "monthly"
    risk_overrides: dict = Field(default_factory=dict)

    def __post_init__(self):
        if self.rebalance_frequency not in _REBALANCE_FREQUENCIES:
            raise ValueError(
                f"rebalance_frequency must be one of {sorted(_REBALANCE_FREQUENCIES)}, "
                f"got {self.rebalance_frequency!r}"
            )
        if not self.models:
            raise ValueError("Strategy must have at least one model")


def load_mandate(name: str, mandates_dir: Optional[Path] = None) -> "Mandate":
    """Load mandate from YAML file."""
    base = mandates_dir or Path("mandates")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Mandate not found: {path}")
    data = _load_yaml(path)
    _validate_no_unknown_keys(data, {
        "name", "description", "market_id", "max_position_pct", "max_sector_pct",
        "max_positions", "min_cash_pct", "benchmark", "risk_free_rate",
        "rebalance_frequency", "allowed_sectors", "excluded_sectors", "custom_constraints"
    }, f"Mandate {name}")
    return Mandate(**data)


def load_universe(name: str, universes_dir: Optional[Path] = None) -> "Universe":
    """Load universe from YAML file."""
    base = universes_dir or Path("universes")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Universe not found: {path}")
    data = _load_yaml(path)
    _validate_no_unknown_keys(data, {
        "name", "market_id", "tickers", "description", "source", "last_updated",
        "as_of", "approximate"
    }, f"Universe {name}")
    universe = Universe(**data)
    
    # Warn if ticker count doesn't match nominal size
    nominal_counts = {
        "nifty10": 10,
        "nifty50": 50,
        "nifty100": 100,
    }
    expected = nominal_counts.get(name)
    if expected is not None and len(universe.tickers) != expected:
        import warnings
        warnings.warn(
            f"Universe '{name}' has {len(universe.tickers)} tickers, "
            f"expected {expected}. Check for duplicates or malformed symbols.",
            UserWarning,
            stacklevel=2
        )
    
    return Universe(**data)


def load_strategy(name: str, strategies_dir: Optional[Path] = None) -> "Strategy":
    """Load strategy from YAML file."""
    base = strategies_dir or Path("strategies")
    path = base / f"{name}.yaml"
    if not path.exists():
        raise ConfigurationError(f"Strategy not found: {path}")
    data = _load_yaml(path)
    _validate_no_unknown_keys(data, {
        "name", "description", "market_id", "models", "blend_policy",
        "capital_slice", "rebalance_frequency", "risk_overrides"
    }, f"Strategy {name}")
    return Strategy(**data)


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}