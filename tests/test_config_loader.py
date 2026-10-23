"""
Test config loader precedence: env > user config > defaults.

Protects the rule that configuration is loaded with correct precedence,
mandate/universe/strategy loaders validate, and broken YAML is rejected clearly.
"""

import pytest
import tempfile
import os
from pathlib import Path

from niveshdristi.config import load_config, get_config, reset_config
from niveshdristi.config_loader import (
    load_mandate,
    load_universe,
    load_strategy,
    load_layered_config,
    Mandate,
    Universe,
    Strategy,
)
from niveshdristi.core.errors import ConfigurationError


class TestConfigPrecedence:
    """Config loader respects precedence: env > user config > defaults."""

    def test_env_overrides_user_config(self, tmp_path, monkeypatch):
        """OPENROUTER_API_KEY env var overrides config.yaml."""
        # Create user config
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
genai:
  api_key: "from_yaml"
""")
        # Set env var
        monkeypatch.setenv("OPENROUTER_API_KEY", "from_env")

        cfg = load_layered_config(user_config_path=str(config_file))
        from niveshdristi.config import Settings
        cfg = Settings(**cfg)
        assert cfg.genai.api_key == "from_env"

    def test_user_config_overrides_defaults(self, tmp_path):
        """User config.yaml overrides defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
backtest:
  initial_capital: 5000000
""")

        cfg = load_layered_config(user_config_path=str(config_file))
        from niveshdristi.config import Settings
        cfg = Settings(**cfg)
        assert cfg.backtest.initial_capital == 5_000_000

    def test_defaults_when_no_config(self):
        """Defaults used when no config file provided."""
        cfg = load_layered_config(user_config_path="/nonexistent/path.yaml")
        from niveshdristi.config import Settings
        cfg = Settings(**cfg)
        # Should have default values
        assert cfg.backtest.initial_capital == 1_000_000
        assert cfg.backtest.risk_free_rate == 0.07

    def test_database_url_env_overrides(self, tmp_path, monkeypatch):
        """DATABASE_URL env var overrides config.yaml."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
data:
  cache:
    pg_dsn: "from_yaml"
""")
        monkeypatch.setenv("DATABASE_URL", "postgresql://from_env")
        # Note: config.py handles DATABASE_URL -> data.cache.pg_dsn
        cfg = load_layered_config(user_config_path=str(config_file))
        from niveshdristi.config import Settings
        cfg = Settings(**cfg)
        assert cfg.data.cache.pg_dsn == "postgresql://from_env"


class TestMandateLoader:
    """Mandate loader validates and loads YAML."""

    def test_load_valid_mandate(self, tmp_path):
        """Valid mandate YAML loads correctly."""
        mandate_file = tmp_path / "test_mandate.yaml"
        mandate_file.write_text("""
name: "test_mandate"
description: "Test mandate"
market_id: "IN_NSE"
max_position_pct: 0.10
max_sector_pct: 0.30
max_positions: 20
min_cash_pct: 0.05
benchmark: "^NSEI"
risk_free_rate: 0.07
rebalance_frequency: "monthly"
""")
        mandate = load_mandate("test_mandate", mandates_dir=tmp_path)
        assert isinstance(mandate, Mandate)
        assert mandate.name == "test_mandate"
        assert mandate.max_position_pct == 0.10
        assert mandate.max_positions == 20

    def test_mandate_not_found_raises(self, tmp_path):
        """Missing mandate raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Mandate not found"):
            load_mandate("nonexistent", mandates_dir=tmp_path)

    def test_mandate_missing_required_field(self, tmp_path):
        """Mandate missing required field raises."""
        mandate_file = tmp_path / "bad_mandate.yaml"
        mandate_file.write_text("name: test\n")  # missing required fields
        with pytest.raises(Exception):  # ValidationError or similar
            load_mandate("bad_mandate", mandates_dir=tmp_path)


class TestUniverseLoader:
    """Universe loader validates and loads YAML."""

    def test_load_valid_universe(self, tmp_path):
        """Valid universe YAML loads correctly."""
        universe_file = tmp_path / "test_universe.yaml"
        universe_file.write_text("""
name: "test_universe"
market_id: "IN_NSE"
tickers:
  - "RELIANCE"
  - "TCS"
  - "HDFCBANK"
""")
        universe = load_universe("test_universe", universes_dir=tmp_path)
        assert isinstance(universe, Universe)
        assert universe.name == "test_universe"
        assert universe.tickers == ["RELIANCE", "TCS", "HDFCBANK"]

    def test_universe_not_found_raises(self, tmp_path):
        """Missing universe raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Universe not found"):
            load_universe("nonexistent", universes_dir=tmp_path)


class TestStrategyLoader:
    """Strategy loader validates and loads YAML."""

    def test_load_valid_strategy(self, tmp_path):
        """Valid strategy YAML loads correctly."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("""
name: "test_strategy"
description: "Test strategy"
market_id: "IN_NSE"
models:
  - model_id: "model1"
    weight: 0.6
    params: {}
  - model_id: "model2"
    weight: 0.4
    params: {}
blend_policy: "weighted_avg"
capital_slice: 1.0
rebalance_frequency: "monthly"
""")
        strategy = load_strategy("test_strategy", strategies_dir=tmp_path)
        assert isinstance(strategy, Strategy)
        assert strategy.name == "test_strategy"
        assert len(strategy.models) == 2
        assert strategy.blend_policy == "weighted_avg"

    def test_strategy_not_found_raises(self, tmp_path):
        """Missing strategy raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Strategy not found"):
            load_strategy("nonexistent", strategies_dir=tmp_path)


class TestBrokenYAMLRejected:
    """Broken YAML is rejected with clear error."""

    def test_syntax_error_yaml(self, tmp_path):
        """YAML syntax error raises clear error."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{ invalid yaml [")
        with pytest.raises(Exception):  # yaml.YAMLError or similar
            load_config(user_config_path=str(bad_file))

    def test_mandate_yaml_syntax_error(self, tmp_path):
        """Mandate with YAML syntax error raises clear error."""
        bad_file = tmp_path / "bad_mandate.yaml"
        bad_file.write_text("{ invalid [")
        with pytest.raises(Exception):
            load_mandate("bad_mandate", mandates_dir=tmp_path)


class TestExampleFiles:
    """Example mandate, universe, strategy files validate."""

    def test_example_mandate(self):
        """Example mandate in mandates/core.yaml validates."""
        from pathlib import Path
        mandate = load_mandate("core", mandates_dir=Path("mandates"))
        assert isinstance(mandate, Mandate)
        assert mandate.name == "core"

    def test_example_universes(self):
        """Example universes validate."""
        from pathlib import Path
        for name in ["nifty10", "nifty50", "nifty100"]:
            universe = load_universe(name, universes_dir=Path("universes"))
            assert isinstance(universe, Universe)
            assert universe.name == name
            assert len(universe.tickers) > 0

    def test_example_strategy(self):
        """Example strategy validates."""
        from pathlib import Path
        strategy = load_strategy("signal_based", strategies_dir=Path("strategies"))
        assert isinstance(strategy, Strategy)
        assert strategy.name == "signal_based"
        assert len(strategy.models) > 0

class TestEnvVarExpansion:
    """'${NAME}' string values expand from the environment (P2-S1)."""

    def _write_config(self, tmp_path: Path) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "data:\n  cache:\n    pg_dsn: \"${P2_TEST_DSN}\"\n", encoding="utf-8"
        )
        return cfg

    def test_expansion_applied_when_set(self, tmp_path):
        """Set variable: value is replaced by the env value."""
        cfg = self._write_config(tmp_path)
        raw = load_layered_config(
            user_config_path=cfg, defaults_path=cfg, env={"P2_TEST_DSN": "postgresql://x/y"}
        )
        assert raw["data"]["cache"]["pg_dsn"] == "postgresql://x/y"

    def test_unset_variable_kept_literal_with_warning(self, tmp_path, capsys):
        """Unset variable: literal kept, warning names ONLY the variable."""
        cfg = self._write_config(tmp_path)
        raw = load_layered_config(user_config_path=cfg, defaults_path=cfg, env={})
        assert raw["data"]["cache"]["pg_dsn"] == "${P2_TEST_DSN}"
        err = capsys.readouterr().err
        assert "P2_TEST_DSN" in err
        assert "postgresql" not in err  # never any resolved value in output

    def test_partial_and_non_string_values_untouched(self, tmp_path):
        """Only whole-string '${NAME}' expands; embedded refs, ints, lists pass through."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "a: \"prefix-${NOPE}\"\n"
            "b: 5\n"
            "c:\n  - \"${SET_VAR}\"\n"
            "d: \"${9BAD}\"\n",
            encoding="utf-8",
        )
        raw = load_layered_config(
            user_config_path=cfg, defaults_path=cfg, env={"SET_VAR": "v"}
        )
        assert raw["a"] == "prefix-${NOPE}"   # not whole-string: untouched
        assert raw["b"] == 5
        assert raw["c"] == ["v"]              # expanded inside lists
        assert raw["d"] == "${9BAD}"          # invalid name form: untouched
