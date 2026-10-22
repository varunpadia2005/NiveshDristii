# NiveshDristi — Rebuild Progress Tracker

**Branch:** `rebuild/v2`  
**Started:** 2026-10-22  
**Target:** India-first (NSE/BSE), global-ready by design

---

## Phase Status

| Phase | Description | Status | Started | Completed | Notes |
|-------|-------------|--------|---------|-----------|-------|
| **0** | Audit & safety net | 🟢 **DONE** | 2026-10-22 | 2026-10-22 | Branch created, audit written, fixtures planned, docs created |
| **1** | Core domain + MarketProfile + packaging | 🟢 **DONE** | 2026-10-22 | 2026-10-22 | Core types, MarketProfile, IN_NSE profile, CLI, validation |
| **2** | Data layer (providers, cache, PIT, calendar) | ⬜ Pending | — | — | Verify NSE bhavcopy library works on Windows |
| **3** | Alpha models (port existing + new quant + India) | ⬜ Pending | — | — | Keep characterization tests green |
| **4** | Portfolio, risk gates, execution, costs/tax | ⬜ Pending | — | — | Deterministic risk gates, India cost model |
| **5** | Engine `advance`, backtest, validation gate | ⬜ Pending | — | — | Walk-forward, deflated Sharpe, PBO |
| **6** | Paper fund, ledger, scheduler, kill switch | ⬜ Pending | — | — | Hash-chained ledger, idempotent tick |
| **7** | LLM layer (multi-provider, personas, validator) | ⬜ Pending | — | — | Default Ollama for dev |
| **8** | Streamlit thin client + CLI polish | ⬜ Pending | — | — | 6 pages, as-of stamps, disclaimer |
| **9** | Global readiness proof (US profile) | ⬜ Pending | — | — | Zero edits to core/engine |
| **10** | Hardening (CI, docs, performance) | ⬜ Pending | — | — | GitHub Actions, coverage, final checklist |

---

## Phase 1 Checklist

- [x] Create `src/niveshdristi/core/` with frozen Pydantic v2 models: `Instrument`, `Signal`, `AlphaModel`, `Decision`, `Order`, `Fill`, `SessionRecord`, errors
- [x] Create `src/niveshdristi/markets/` with `MarketProfile`, `MarketRegistry`, and full `IN_NSE` profile
- [x] Create `markets/in_nse/` YAML files: `holidays_in.yaml`, `costs.yaml`, `tax.yaml`, `sectors.yaml`, `asm_gsm.yaml`, `fno_ban.yaml`, `profile.py`
- [x] Config loader with precedence: env > user config > defaults; YAML schemas for `mandates/`, `universes/`, `strategies/`
- [x] `nd` CLI skeleton (Typer) with `--json` output mode: `config`, `data`, `signals`, `backtest`, `paper`, `validate`, `version`
- [x] Validation: `nd validate` with market literals scan for `core/` and `engine/`
- [x] Engine stub: `advance()` skeleton in `src/niveshdristi/engine/`
- [x] Mandates/universes/strategies YAML examples: `mandates/core.yaml`, `universes/nifty10/50/100.yaml`, `strategies/signal_based.yaml`
- [x] Characterization tests still pass (16/16)
- [x] `nd validate` passes (no market-specific literals in core/engine)
- [x] All 16 tests pass
- [x] Streamlit and FastAPI entry points load OK
- [x] `nd --json version` works
- [x] Updated `pyproject.toml` with `typer`, `rich`; removed Poetry remnants

---

## Phase 0 Checklist

- [x] Create branch `rebuild/v2`
- [x] Inventory repo: modules, entry points, dependencies
- [x] Write `docs/AUDIT.md` with module map, bugs, conflicts
- [x] Plan characterization tests (fixtures defined in AUDIT.md)
- [x] Create `docs/DISCLAIMER.md`
- [x] Create `docs/PROGRESS.md` (this file)
- [x] Create `docs/VERIFY.md`
- [x] Create `docs/CHANGES.md` (copied from downloaded spec)
- [x] Write characterization tests in `tests/test_characterization.py`
- [x] Save fixtures to `tests/fixtures/`
- [x] Run `ruff check`, `mypy`, `pytest`
- [x] Commit Phase 0

---

## Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-22 | Use **uv** for packaging (Phase 1) | Faster, single binary, PEP 621 native, Windows-friendly; current pyproject.toml has Poetry remnants — will migrate |
| 2026-10-22 | Keep PostgreSQL optional | Spec prefers Parquet/DuckDB for local cache; PG only for shared environments |
| 2026-10-22 | Move existing code to `legacy/` after tests | Non-negotiable rule #8: don't delete in first pass |

---

## Open Questions / Risks

| # | Question | Risk Level | Status |
|---|----------|------------|--------|
| 1 | Which NSE bhavcopy library works on Windows? (`jugaad-data`, `nsepython`, or official?) | 🔴 High | Need live check in Phase 2 |
| 2 | Source for India 10Y G-sec yield (not US ^TNX proxy)? | 🟡 Medium | Need to find in Phase 2 |
| 3 | Are all `SECTOR_ETFS` tickers available on yfinance? | 🟡 Medium | Verify in Phase 1/2 |
| 4 | Corporate action announcement dates (not just ex-dates) — free source? | 🟡 Medium | May need stub + licensed provider later |
| 5 | SEBI ASM/GSM exclusion lists — programmatic access? | 🟡 Medium | May need manual YAML + refresh process |
| 6 | Poetry vs uv — user preference? | 🟢 Low | Will propose uv in Phase 1 report |

---

## Definition of Done (v1, India) — from CHANGES.md §12

- [ ] `nd backtest mandates/core.yaml --universe nifty100 --start 2018-01-01` runs offline from cache, prints net-of-cost results vs Nifty TRI with validation-gate verdict
- [ ] `nd paper create/tick/status/halt/resume` works, idempotent, ledger verifies
- [ ] Every existing analytic is an `AlphaModel`; ≥5 new ones, ≥3 India-specific
- [ ] LLM narrator produces grounded, schema-valid theses; lying-LLM test passes
- [ ] Streamlit app has 6 pages with as-of stamps and disclaimers
- [ ] `US` profile smoke test passes with zero edits to `core/` and `engine/`
- [ ] CI green, no network calls in tests

---

*Update this file after each phase completion.*