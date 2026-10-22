# NiveshDristi — Phase 0 Audit Report

**Branch:** `rebuild/v2`  
**Date:** 2026-10-22  
**Auditor:** Lead Engineer (AI)

---

## 1. Module Map

### 1.1 Source Layout (`src/niveshdristi/`)

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `config.py` | Pydantic Settings loader (env > yaml > defaults) | `Settings`, `CFG` global |
| `data/` | Data layer: providers, cache, adjust, validate, loader, universe, macro | `providers.py`, `cache.py`, `loader.py`, `contracts.py`, `universe.py`, `macro.py` |
| `indicators/` | Polars-expression technical indicators (vectorized, no loops) | `technical.py`, `registry.py` |
| `signals/` | Signal engine (4-group scorer), conviction blending | `engine.py`, `conviction.py` |
| `fundamentals/` | yfinance `.info` fetcher + PG cache, guardrail rules | `loader.py` |
| `regime/` | RRG sector rotation, market state classifier | `rrg.py` |
| `backtest/` | Event-driven backtest with 1-day delay, Indian cost model | `engine.py` |
| `genai/` | OpenRouter client, analyst note generator, number validator | `client.py`, `analyst.py`, `validator.py`, `templates/analyst_note.j2` |
| `api/` | FastAPI endpoints (health, price, signal, fundamentals, regime, analyst, backtest) | `main.py` |
| `app/` | Streamlit multipage UI (8 pages) + components | `main.py`, `pages/*.py`, `components.py` |

### 1.2 Entry Points

| Entry | Command | Description |
|-------|---------|-------------|
| Streamlit UI | `streamlit run src/niveshdristi/app/main.py` | Main UI (port 8501) |
| FastAPI | `uvicorn niveshdristi.api.main:app --reload` | REST API (port 8000) |
| Docker Compose | `docker-compose up --build` | Full stack (PG + API + UI) |
| Tests | `pytest tests/` | Import/smoke tests |

### 1.3 Dependencies (from `pyproject.toml`)

**Core:** polars, duckdb, yfinance, fastapi, uvicorn, streamlit, httpx, pydantic, pydantic-settings, pyyaml, jinja2, python-dotenv, asyncpg, lightgbm, optuna, numpy, pandas  
**Dev:** pytest, pytest-asyncio, pytest-cov, ruff, black, mypy, pre-commit

---

## 2. What Works

| Feature | Status | Notes |
|---------|--------|-------|
| Technical indicators (RSI, MACD, BB, ATR, ADX, OBV, EMAs) | ✅ Working | Polars expressions, vectorized, configurable via `config.yaml` |
| Signal engine (4-group: trend, momentum, volatility, volume) | ✅ Working | Composite ∈ [-1, +1], plain-English reasons |
| Conviction scoring (technical + fundamental + regime + ML) | ✅ Working | Weighted blend, guardrail caps |
| Fundamental data (yfinance `.info`) | ✅ Working | Weekly PG cache, guardrail rules from config |
| RRG sector rotation | ✅ Working | 8 NSE sector ETFs vs Nifty benchmark |
| Market regime (bull/choppy/bear) | ✅ Working | 60-day return + 20-day vol + VIX |
| Backtest engine | ✅ Working | 1-day delay mandatory, cost model from config, walk-forward |
| GenAI analyst (OpenRouter) | ✅ Working | JSON output, Jinja2 deterministic fallback |
| Number validator | ✅ Working | Extracts numbers from LLM output, verifies against facts bundle |
| Streamlit UI (8 pages) | ✅ Working | Dashboard, Deep-Dive, Screener, Sector Rotation, Backtest Lab, Portfolio, AI Analyst, Methodology |
| FastAPI endpoints | ✅ Working | All major data/signals/analyst/backtest routes |
| Config system | ✅ Working | YAML + env overrides, Pydantic validation |

---

## 3. Bugs / Issues Found

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | **Look-ahead in fundamentals**: `as_of` = `date.today()` in `fetch_yfinance_fundamentals()` — uses current date, not announcement date | 🔴 Critical | `fundamentals/loader.py:101` |
| 2 | **No point-in-time store**: Fundamentals lack `announced_at`; queries don't take `as_of` parameter | 🔴 Critical | `fundamentals/loader.py`, `data/contracts.py` |
| 3 | **Survivorship bias**: `NIFTY50` list is current (2024); backtest uses today's constituents for historical periods | 🔴 Critical | `data/universe.py:8-19` |
| 4 | **Hard-coded NSE holidays**: Only 2024 holidays; no mechanism to load/extend | 🟡 High | `data/universe.py:50-64` |
| 5 | **yfinance hard-wired everywhere**: Provider suffix `.NS` in `get_ticker_suffix()`, `YFinanceProvider.fetch()`, `MACRO_TICKERS` | 🟡 High | `data/loader.py:34`, `data/providers.py:48`, `data/macro.py:9-14` |
| 6 | **India-specific values in core/engine**: `SECTOR_ETFS` uses `.NS` suffixes; `market_regime` assumes Nifty/VIX | 🟡 High | `regime/rrg.py:8-29`, `regime/rrg.py:75-89` |
| 7 | **Cost model in `config.yaml` only**: Not in `markets/in_nse/costs.yaml` as spec requires; no `# VERIFY` tags | 🟡 High | `config.yaml:86-94` |
| 8 | **No `MarketProfile` abstraction**: Engine takes config directly, no market-agnostic interface | 🟡 High | `backtest/engine.py`, `signals/engine.py` |
| 9 | **LLM provider hard-coded**: Only OpenRouter; no factory for Anthropic/OpenAI/Google/Ollama | 🟠 Medium | `genai/client.py:9-20` |
| 10 | **No hash-chained ledger / kill switch / paper fund**: Not implemented | 🟠 Medium | Missing entirely |
| 11 | **No validation gate (deflated Sharpe, PBO, CPCV)**: Walk-forward exists but no overfitting detection | 🟠 Medium | `backtest/engine.py:141-170` |
| 12 | **`backtest_lab.py` has duplicate `render` function** | 🟢 Low | `app/pages/backtest_lab.py:10,143` |
| 13 | **No `as_of` timestamp on UI pages**: Only disclaimer shown | 🟢 Low | `app/pages/*.py` |
| 14 | **Price-range engine**: Placeholder only (tab exists but no real engine) | 🟢 Low | `app/pages/deep_dive.py:255-280` |
| 15 | **No CLI (`nd`)**: Only API + UI | 🟢 Low | Missing |
| 16 | **Tests are smoke-only**: No characterization tests freezing current outputs | 🟢 Low | `tests/test_imports.py` |

---

## 4. Look-Ahead / Survivorship Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| **Fundamentals `as_of` = today** | `fetch_yfinance_fundamentals()` sets `as_of=date.today()` — a backtest on 2023-01-01 would see fundamentals "as of 2026" | Invalidates all backtests using fundamentals |
| **No `announced_at` field** | `FundamentalData` has only `as_of` (period end), not announcement date; SEBI requires results within 45-60 days | Cannot enforce PIT discipline |
| **Current Nifty 50 universe** | `NIFTY50` list is static 2024 composition; delisted names excluded | Survivorship bias inflates returns |
| **Adjusted prices from yfinance** | `adjust_prices()` uses yfinance `adj_close` which may incorporate future corporate actions | Potential look-ahead in price series |

---

## 5. Hard-Coded yfinance Dependencies

| Location | Hard-Coded Element |
|----------|-------------------|
| `data/loader.py:34-38` | `get_ticker_suffix()` adds `.NS` |
| `data/providers.py:48` | `YFinanceProvider` adds `.NS` for non-index tickers |
| `data/providers.py:92` | `get_universe()` returns config universe directly |
| `data/macro.py:9-14` | `MACRO_TICKERS` uses yfinance symbols (`^INDIAVIX`, `INR=X`, `CL=F`, `^TNX`) |
| `regime/rrg.py:8-29` | `SECTOR_ETFS` uses `.NS` suffixed sector ETF tickers |
| `api/main.py:91, 114` | Hard-coded `^NSEI` for Nifty, sector ETFs |
| `fundamentals/loader.py:83` | Adds `.NS` suffix for yfinance |

---

## 6. Hard-Coded India-Specific Values

| Location | Value | Should Be In |
|----------|-------|--------------|
| `config.yaml:86-94` | All cost rates (brokerage, STT, exchange, SEBI, stamp, GST, slippage) | `markets/in_nse/costs.yaml` with `# VERIFY` |
| `config.yaml:96` | `signal_delay_days: 1` | `markets/in_nse/rules.yaml` |
| `config.yaml:78` | `benchmark: "^NSEI"` | `markets/in_nse/profile.py` |
| `regime/rrg.py:8-29` | Sector ETF tickers (`.NS`) | `markets/in_nse/sectors.yaml` |
| `data/universe.py:50-64` | 2024 NSE holidays only | `markets/in_nse/holidays_in.yaml` |
| `fundamentals/loader.py:83` | `.NS` suffix logic | Provider adapter only |
| `signals/engine.py:15` | ADX threshold 25 | Config or model-specific |
| `signals/conviction.py:46` | Regime score map (bull=80, choppy=50, bear=20) | Config or model-specific |

---

## 7. Frontend Weaknesses

| Weakness | Detail |
|----------|--------|
| **Not a thin client** | Pages call `api_get()` but also directly import and run `load_prices()`, `compute_all_indicators()`, `generate_signal_report()` (e.g., `deep_dive.py:48-54`) |
| **Blocking LLM calls on page load** | `deep_dive.py:232-251` calls `/analyst/{ticker}` on button click but no async/streaming; UI freezes |
| **No caching** | `st.cache_data` not used; every widget interaction re-fetches data |
| **No "as of" timestamps** | Only disclaimer shown; no data freshness indicators |
| **Duplicate code** | `backtest_lab.py` has two `render()` functions |
| **Hard-coded ₹ symbol** | `dashboard.py:83`, `deep_dive.py:76`, `backtest_lab.py:30` — violates global-ready rule |
| **No dark/light theme verification** | Theme toggle exists but components use CSS variables — need to verify both themes |

---

## 8. Conflicts / Questions

| # | Conflict / Question | Spec Reference | Recommendation |
|---|---------------------|----------------|----------------|
| 1 | **Packaging: Poetry vs uv** | Phase 1 says "tell me which you chose and why" | Recommend **uv** (faster, single binary, PEP 621 native, works well on Windows); but current `pyproject.toml` has Poetry-style `[tool.poetry.group.dev.dependencies]` — need decision |
| 2 | **PostgreSQL requirement** | Spec doesn't mandate PG; current code uses asyncpg + PG for cache | Keep PG optional (fallback to Parquet/DuckDB); spec prefers Parquet/DuckDB for local cache |
| 3 | **Macro tickers** | Spec says avoid scraping; `^TNX` (US 10Y) is a proxy for India G-sec | Need proper India 10Y G-sec source (NSE `^NSE10Y`?) or FRED via API |
| 4 | **Sector ETF availability** | `SECTOR_ETFS` tickers may not all exist on yfinance | Verify each; fallback to constituent-based sector indices |
| 5 | **Existing `price_range` contract** | `data/contracts.py:44-52` has `PriceRange` but no implementation | Port to `alpha/india/price_range.py` as AlphaModel |
| 6 | **ML pipeline** | `models` config section exists but no ML alpha model yet | Phase 3 will add; keep config for now |
| 7 | **Windows path handling** | Uses `pathlib` throughout — good | Verify no bash-only scripts; `Makefile` exists but not used in CI |
| 8 | **`docs/CHANGES.md` missing** | Master prompt says copy from Downloads | Will create from downloaded spec in Phase 0 |

---

## 9. Characterization Test Plan (Phase 0 Task 3)

| Function | Fixture Input | Expected Output (frozen) |
|----------|---------------|--------------------------|
| `compute_all_indicators()` | 10-day OHLCV DataFrame | DataFrame with all indicator columns |
| `generate_signal_report()` | DataFrame with indicators | `SignalReport` with composite ∈ [-1,1] |
| `check_guardrails()` | `FundamentalData` with various metrics | `GuardrailReport` with correct `max_score_cap` |
| `compute_conviction()` | SignalReport + GuardrailReport + RegimeReport | `ConvictionScore` 0-100 |
| `simulate()` (backtest) | Prices + signals dict | `BacktestResult` with metrics dict |
| `market_regime()` | Nifty DataFrame + VIX | "bull" / "choppy" / "bear" |
| `compute_rrg()` | Sector data + benchmark | Quadrant dict per sector |
| `validate_note()` | AnalystNote + FactsBundle | (bool, errors_list) |
| `render_template()` | Template + context | Rendered string with expected sections |

Fixtures to save in `tests/fixtures/`:
- `prices_10d.parquet` — 10 days of synthetic OHLCV
- `fundamentals_sample.json` — sample FundamentalData
- `signals_sample.json` — sample SignalReport
- `regime_sample.json` — sample RegimeReport

---

## 10. Required Docs to Create (Phase 0 Task 4)

| File | Status | Content |
|------|--------|---------|
| `docs/DISCLAIMER.md` | 📝 To create | Standard educational disclaimer (from README + master prompt) |
| `docs/PROGRESS.md` | 📝 To create | Phase tracker with checkboxes |
| `docs/VERIFY.md` | 📝 To create | List of all `# VERIFY` rates from CHANGES.md + config.yaml |
| `docs/CHANGES.md` | 📝 To create | Copy from `NiveshDristi_CHANGES_from_ai-hedge-fund.md` (Downloads) |

---

## 11. Next Steps (Phase 0 Completion)

1. ✅ Create branch `rebuild/v2`
2. 📝 Write `docs/AUDIT.md` (this file)
3. 📝 Create characterization tests + fixtures
4. 📝 Create `docs/DISCLAIMER.md`, `docs/PROGRESS.md`, `docs/VERIFY.md`, `docs/CHANGES.md`
5. 📝 Run tests + linters (`ruff check`, `mypy`, `pytest`)
6. 📝 Commit and report

---

*End of Audit Report*