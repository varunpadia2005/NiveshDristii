# Phase 2 Prerequisites

## 1. 2026 Holidays Missing (Strict XFail)
The `holidays_in.yaml` calendar file does not contain 2026 holidays. The test `test_holidays_yaml_covers_current_year` in `tests/test_market_profile.py` is marked with `@pytest.mark.xfail(strict=True, reason="Phase 2: fill 2026 holidays from the NSE official list")`.

**Action Required**: Download the official NSE 2026 holiday list and update `markets/in_nse/holidays_in.yaml` with the 2026 holidays and `years_covered: [2024, 2025, 2026]`.

## 2. Universe Ticker Counts Need As-Of Index Constituents
- `nifty50` universe has 49 tickers (expected 50)
- `nifty100` universe has 101 tickers (expected 100)

The universe YAML files in `universes/` need to be updated with the correct as-of date index constituents from NSE. The `as_of` and `source` metadata fields should be populated.

**Action Required**: 
- Fetch official NSE index constituents for Nifty 50 and Nifty 100 as of a specific date
- Update `universes/nifty50.yaml` and `universes/nifty100.yaml` with correct tickers and metadata

## 3. pg_dsn Returns Literal '${DATABASE_URL}'
The `pg_dsn` config value returns the literal string '${DATABASE_URL}' instead of expanding the environment variable. This is because pydantic_settings doesn't automatically expand environment variable references in nested config structures.

**Action Required**: Implement environment variable expansion in the config loader for the `data.cache.pg_dsn` field.

## 4. Phase 0 Latent Bugs (From Characterization Tests)
- `backtest.costs` and `backtest.timing` attribute access crash
- Dead `_compute_cost_bps` function
- Flat `cost_bps=15` hardcoded instead of using cost model

**Action Required**: These are known issues in the legacy backtest module that will be addressed during Phase 2 refactoring.

## 5. Unverified Rates in docs/VERIFY.md
- `stt_delivery_sell_pct` naming inconsistency (should be `stt_delivery_sell_pct` or `stt_delivery_pct`)
- `exchange_charges_pct` rate verification needed against current NSE circulars

**Action Required**: Verify all cost model rates against current NSE/SEBI circulars and update `markets/in_nse/profile.py` CostModel accordingly.

## 6. Legacy Mypy and Ruff Baselines
The legacy packages (backtest, data, signals, indicators, app, api, fundamentals, genai, regime) have existing mypy and ruff errors that are not addressed in Phase 1.

**Action Required**: Phase 2 will address technical debt in legacy packages incrementally.

## 7. Python Version
Phase 1 uses Python 3.13.7 (pydantic 2.13.5, mypy 2.4.0). Phase 2 should consider pinning to Python 3.11 as per pyproject.toml target.

## 8. CLI Command Status
- `nd paper/*` commands: STUBS (not implemented)
- `nd backtest/*` commands: STUBS (not implemented)
- `nd signals/*` commands: STUBS (not implemented)
- `nd data/*` commands: STUBS (not implemented)
- `nd config --show --validate`: REAL (working)
- `nd validate`: REAL (working)
- `nd version`: REAL (working)

**Action Required**: Implement paper trading, backtest, signals, and data commands in Phase 2.