# Phase 1 Progress Report

## Summary
Phase 1 complete: Typed CFG, config loader with precedence, removed dead _ConfigProxy, added new scaffolding.

## Test Results
- **110 passed, 1 xfailed, 111 collected**
- All 16 original characterization tests pass
- mypy clean on core/ (7 files)
- ruff clean on new code paths (core, markets, cli, engine, config_loader)

## Key Achievements

### 1. Config Encoding Fix (commit e230a39)
- Added `encoding="utf-8"` to all `open()` calls in config.py

### 2. Core Types to Pydantic v2 Frozen BaseModel (commit 9cf9c85)
- 7 files converted: instrument.py, signal.py, alpha.py, decision.py, session.py, errors.py, __init__.py
- No `@dataclass` decorators
- `arbitrary_types_allowed=True` only where needed (Signal, SessionRecord, AsOfContext, Fill - for forward refs and Any)
- Justification comments added above each `arbitrary_types_allowed`

### 3. Config Layered Loader + Strategy.rebalance_frequency + Holiday years_covered (commit 49bddd7)
- New `config_loader.py` with:
  - `load_layered_config()` - env > user config > defaults precedence
  - `load_mandate()`, `load_universe()`, `load_strategy()` - YAML loaders with validation
  - New dataclasses: Mandate, Universe, Strategy
  - Universe metadata: as_of, source, approximate
  - Strategy.rebalance_frequency field
  - Holiday years_covered in IN_NSE profile

### 4. CLI Validate Command + Config Show (commit e099b95)
- `nd validate` with 8 validation checks
- `--json validate` exits 0 on success, 1 on failure
- `nd config --show` works without config file
- Unknown key detection in config YAML

### 5. Tests Updated (commit 87c8bf1)
- Core types tests with Pydantic ValidationError checks
- Profile tests with holiday coverage xfail (strict=True)
- Config loader tests using load_layered_config
- CLI tests for help, JSON output, subcommands, validate
- Literal guard tests using tmp_path

### 6. Docs Updated (commit 87c8bf1)
- PROGRESS.md with honest baselines
- AUDIT.md with merge history

### 7. Scanner Tests Pass (13/13)
- Uses tmp_path for isolation
- encoding="utf-8" on all I/O
- FORBIDDEN_PATTERNS covers NSE, NIFTY, ₹, IST, Kolkata, .NS, .BO
- Real core/ and engine/ have 0 findings

### 8. Config Equality Proven
- MD5 match: 0f2ad5235d7082aaad4a26bf5f1554c3 (Phase 0 and HEAD)

### 9. nd --json Validate Works
- Exits 0 on valid config
- Exits 1 on unknown key in config

## Git Diff Verification
- Legacy folders untouched: `git diff --diff-filter=MD --stat 82f76d8 HEAD -- backtest data signals indicators tests` = empty
- config.py diff from 82af57b: only `encoding="utf-8"` on open()

## Known Issues for Phase 2
See docs/PHASE2_PREREQS.md for complete list:
1. 2026 holidays missing (strict xfail)
2. Universe ticker counts need as-of index constituents
3. pg_dsn env var expansion
4. Legacy backtest latent bugs
5. Unverified cost model rates
6. Legacy mypy/ruff baselines

## Environment
- Python: 3.13.7
- Pydantic: 2.13.5
- mypy: 2.4.0
- pytest: 8.3.4
- ruff: 0.5.x