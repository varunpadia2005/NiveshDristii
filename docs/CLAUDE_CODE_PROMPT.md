# NiveshDristi — Master Prompt for Claude Code

**How to use**
1. Copy `NiveshDristi_CHANGES_from_ai-hedge-fund.md` into your repo as `docs/CHANGES.md`.
2. Open Claude Code in `D:\NiveshDristi` and paste everything inside the **MASTER PROMPT** block below.
3. Claude Code will do Phase 0 (audit) and stop. Review, then send the one-liner for the next phase (see the end of this file).

---

## MASTER PROMPT (paste this)

```
You are the lead engineer on NiveshDristi, an AI-assisted portfolio research tool for the INDIAN market (NSE/BSE) that must later expand to global markets. It is for personal/educational use only. It is NOT investment advice.

## Context
- Existing project (Python): technical analysis (RSI, MACD, Bollinger Bands, moving averages), fundamental guardrails (P/E, ROE, D/E), sector rotation classification, price range engines, backtesting. Uses yfinance, pandas-ta, Plotly, Streamlit. Current state: incomplete, weak frontend.
- Read `docs/CHANGES.md` fully before doing anything. It is the design spec. It was derived from the architecture docs (README, ROADMAP, VISION) of github.com/virattt/ai-hedge-fund: a persistent "fund" object, one `advance` engine verb shared by backtest and paper modes, a Signal/AlphaModel contract, deterministic risk gates, LLMs that form views but never touch trades, a hash-chained ledger, a kill switch, and a validation gate. We are borrowing IDEAS, not copying code. Do not browse or copy that repo's source; implement from the spec.
- I develop on Windows. Use pathlib, avoid bash-only tooling, and make everything run on Windows, macOS and Linux.

## Non-negotiable rules
1. Point-in-time honesty: on any simulated date, only use data that was public by then. Fundamentals carry `announced_at`; queries take `as_of`.
2. Decide at close of session T, execute at T+1. Never assess and execute against the same price.
3. The LLM never sizes positions or places orders. It produces schema-validated views and narrates. All numbers in any LLM prompt come from code-built evidence packets; any LLM output citing numbers not in the evidence is rejected.
4. Risk gates are plain deterministic Python that nothing can override. Log every clamp with a reason.
5. India defaults: long-only cash equities, T+1, price-band/circuit awareness, ADV liquidity cap, exclusion of surveillance-listed/illiquid names, realistic costs (brokerage, STT, exchange charges, SEBI fee, stamp duty, GST, DP charge) and optional capital-gains tax. ALL market rules and rates live in YAML under `markets/in_nse/`, never in code. Mark any rate you are unsure of with `# VERIFY` and list those in `docs/VERIFY.md`.
6. Global-ready: `core/` and `engine/` must contain zero market-specific literals (no "NSE", "NIFTY", "₹", "IST", ".NS"). Provider suffixes live only inside provider adapters. Add a test that enforces this.
7. Tests run offline using fixtures; no live network in tests. Every module gets unit tests. Keep `ruff` and `mypy` (or pyright) clean.
8. Work in small commits on a branch named `rebuild/v2`. Never delete my existing code in the first pass; move it to `legacy/` once its behaviour is captured by tests and the new version matches it.
9. Do not invent data sources, API endpoints or library functions. If you are unsure a library or endpoint exists or works, verify by installing/inspecting it or tell me, and use a clearly-marked stub with a failing-safe fallback. Do not scrape sites whose terms forbid it.
10. Every UI page and every report shows an "as of" timestamp and the disclaimer text from `docs/DISCLAIMER.md`.
11. Secrets only in `.env` (git-ignored). Provide `.env.example`.
12. If a requirement here conflicts with what you find in my code, don't guess: record it in `docs/AUDIT.md` under "Conflicts / questions" and ask me.

## Working method
- Work phase by phase. After each phase: run tests + linters, update `docs/PROGRESS.md`, commit, then STOP and give me a report in this format:
  1. What was built (files)
  2. How to run/verify it (exact commands)
  3. Test results
  4. Deviations from docs/CHANGES.md and why
  5. Open questions / risks
  6. Next phase proposal
- Do not start the next phase until I say "Proceed to Phase N".
- Prefer boring, readable code with type hints and docstrings that state the *why*.

## PHASE 0 — Audit and safety net  (START HERE)
1. Create branch `rebuild/v2`. Inventory the repo: modules, entry points, dependencies, how the Streamlit app is wired, where indicators/guardrails/sector rotation/price-range/backtest live.
2. Write `docs/AUDIT.md`: module map; what works; bugs; look-ahead or survivorship issues you can see; places where yfinance is hard-wired; places where India-specific values are hard-coded; frontend weaknesses; "Conflicts / questions".
3. Add characterization tests that freeze the CURRENT outputs of the existing indicator, guardrail, sector-rotation and backtest functions on small fixture datasets (save fixtures in `tests/fixtures/`).
4. Create `docs/DISCLAIMER.md`, `docs/PROGRESS.md`, `docs/VERIFY.md`.
5. Stop and report.

## PHASE 1 — Core domain + market abstraction + packaging
- `src/niveshdristi/` layout, `pyproject.toml` (uv or Poetry; tell me which you chose and why), ruff, mypy, pytest, pre-commit.
- `core/`: `Instrument`, `Signal` (conviction in [-1,1], horizon_days, thesis, evidence, model_id, as_of), `AlphaModel` protocol, `Decision`, `Order`, `Fill`, `SessionRecord`, errors. Pydantic v2, frozen models.
- `markets/registry.py`, `MarketProfile`, and the full `IN_NSE` profile (timezone, session, settlement, shorting_allowed=False, calendar loader with `holidays_in.yaml`, `costs.yaml`, `tax.yaml`, `sectors.yaml`, benchmark config). Use `# VERIFY` for rates.
- Config loader (env > user config > defaults). YAML schemas for `mandates/`, `universes/` (nifty50/100/500 files can start as small fixtures + a loader; document how to refresh) and `strategies/`.
- `nd` CLI skeleton (Typer or argparse) with `--json` output mode.
- Test: no market-specific literals in `core/` or `engine/`.

## PHASE 2 — Data layer
- `DataClient` protocol (prices, fundamentals, corporate_actions, index_constituents, flows, filings).
- Providers: `YFinanceClient` (suffix mapping inside adapter only) and an NSE end-of-day bhavcopy provider with delivery quantity (use a maintained library or official files; verify it works before depending on it). Provider chain with ordered fallback, retries, rate-limit handling.
- Local cache (Parquet or DuckDB) with cache keys and staleness rules.
- Corporate actions: store raw and adjusted prices separately; detect split/bonus discontinuities.
- Point-in-time store: `period_end`, `announced_at`, `source`; `as_of` queries; conservative lag fallback when only period-end is known, flagged "approximate PIT".
- Data-quality checks (gaps, zero volume, stale bars, outliers) producing a report object.
- Trading calendar from `holidays_in.yaml` with verification against any library you use.
- Tests: fallback works; cache hit on second call; PIT test proves a result announced tomorrow is invisible today.

## PHASE 3 — Alpha models
- Port EXISTING analytics to `AlphaModel` without changing their maths (characterization tests must still pass): TA ensemble (make weighting regime-aware as an option), fundamental guardrails (quality score + hard exclusions), sector rotation (vs benchmark, emits sector tilt), price-range engine (entry/stop zones as evidence, not a standalone signal).
- New quant models: momentum (time-series + cross-sectional), mean reversion, quality/value factors, low-volatility, earnings-reaction drift on quarterly results, regime detection (start simple: trend/vol states on benchmark + India VIX; HMM optional).
- New India models: promoter holding/pledge trend, delivery-percentage anomaly, FII/DII flow regime, bulk/block deal signal, macro overlay (repo rate direction, INR, crude) with sector sensitivity map in YAML.
- Model registry listing id, horizon, required data, and PIT-safety status. Each model: thesis string + evidence dict + tests.
- Where a data source isn't reliably available yet, implement the model against the protocol with a fixture and mark it `data_status: stub` in the registry rather than faking data.

## PHASE 4 — Portfolio, risk, execution, costs
- Portfolio construction: conviction → target weights, long-only for IN_NSE (clamp negatives to zero based on `shorting_allowed`), optional vol scaling, strategy blending policy from `strategies/*.yaml`.
- `RiskGate` chain: max position, max sector, min cash, ADV cap, turnover cap, exclusion lists, minimum price/market-cap, drawdown circuit. Every clamp is logged.
- Execution: `Broker` protocol, `SimBroker`, `PaperBroker`; integer shares, circuit-limit fill failure, slippage scaled by liquidity, cost model and tax model read from the market profile.
- Tests: extreme conviction on an illiquid stock is clipped with a logged reason; high-turnover strategy loses materially after costs.

## PHASE 5 — Engine, backtest, validation
- `advance(fund, clock, broker, data)`: reconcile → execute pending decision → mark → assess (rebalance days) → record. Same function for backtest and paper.
- Backtest = `advance` looped over the calendar. Metrics: CAGR, vol, Sharpe, Sortino, max drawdown, turnover, hit rate, exposure, cost drag; gross vs net; benchmark comparison (prefer total-return index; document fallback).
- Walk-forward evaluation; parameter sensitivity; regime breakdown.
- Validation gate: deflated Sharpe and probability of backtest overfitting (implement CPCV if feasible, otherwise document the simplified approach used and why).
- Reports as JSON + Plotly HTML.
- Tests: an intentionally overfit toy strategy is flagged by the gate.

## PHASE 6 — Paper fund, ledger, scheduler
- Hash-chained append-only ledger of `SessionRecord`s; replay verifies the chain and rebuilds state; broker book reconciled against the ledger before every tick (mismatch raises, never auto-repairs).
- Kill switch: any exception inside a tick halts the fund; `halt`/`resume`.
- `nd paper create|tick|status|list|halt|resume`; `tick` is idempotent and skips holidays; designed to be called from Windows Task Scheduler or cron after NSE close once EOD data is available.
- `events.jsonl` for every tick/failure/halt/resume; optional Telegram/email notifier behind an interface (off by default); heartbeat file.
- Tests: ticking twice is a no-op; corrupting one ledger line fails verification; replay of a past period equals the backtest records.

## PHASE 7 — LLM layer (GenAI, safely)
- `make_llm(provider, model)` factory: Anthropic, OpenAI, Google, and Ollama (local, free). Structured outputs with Pydantic validation, retries, token/cost logging, on-disk response cache keyed by (prompt hash, evidence hash). Provider/model chosen from config, not hard-coded.
- Evidence packets built by code. A `GroundingValidator` rejects any LLM output that cites a number or fact not in the packet.
- Personas as prompt templates (stylised approximations of public investing philosophies, not endorsements; include the disclaimer): India growth-conviction lens, QGLP lens (Quality, Growth, Longevity, Price), SMILE small-cap lens, Graham-style deep-value lens, and a risk-skeptic that argues against the trade. Plus a neutral Analyst Narrator that explains deterministic signals in plain English.
- LLM analysts run only on a shortlist produced by quant models (cost control).
- Optional, behind a flag: filings/concall RAG (chunk + embed + retrieve) that always shows source snippets.
- Tests: with a mocked LLM the pipeline is deterministic; a "lying LLM" fixture (injects a fake number) is rejected; schema failures retry then fall back safely.

## PHASE 8 — Frontend + CLI polish
Rebuild the Streamlit app as a THIN client over `services/` (the same facade the CLI uses). Pages:
1. Market Overview (benchmark, Bank Nifty, India VIX, sector heatmap, FII/DII flows, regime badge)
2. Stock Deep-Dive (price + indicators, fundamentals card, each analyst's signal + thesis, risk-gate verdicts, entry/stop zones)
3. Signals Board (universe table, filters by sector/conviction/liquidity, "why" drawer)
4. Backtest Lab (mandate, universe, dates; equity vs benchmark; costs; validation-gate verdict)
5. Paper Fund (NAV, positions, decisions with theses, ledger verification status, halt/resume)
6. Settings (LLM provider/model, data providers, market profile, costs)
Rules: `st.cache_data` for expensive calls, no recompute on every widget change, no blocking LLM calls on page load, loading states, as-of stamp and disclaimer on every page, readable in light and dark themes.

## PHASE 9 — Global readiness proof
- Add a `US` market profile (calendar, USD, cost model, shorting_allowed flag, benchmark) and a US data adapter via an available provider.
- Add base-currency/FX groundwork for multi-market NAV.
- Success = backtest runs for both markets with ZERO edits to `core/` and `engine/`. The literal-scan test must still pass.

## PHASE 10 — Hardening
- CI (GitHub Actions) running ruff, mypy, pytest offline; coverage report.
- Docs: `README.md` (install on Windows first), `docs/ARCHITECTURE.md` with diagrams, `docs/ADDING_A_MARKET.md`, `docs/ADDING_AN_ALPHA_MODEL.md`, `docs/VERIFY.md` finalised.
- Performance pass (profiling on a Nifty 500 backtest), logging, error messages.
- Final checklist against "Definition of done" in `docs/CHANGES.md`.

Begin with PHASE 0 now. Do not proceed past it.
```

---

## Phase kick-off one-liners (send after reviewing each report)

- `Proceed to Phase 1. Follow the master prompt rules. Ask me before choosing between uv and Poetry only if Phase 0 found a conflict.`
- `Proceed to Phase 2. Before depending on any NSE data library, run a small live check and tell me what actually works on my machine.`
- `Proceed to Phase 3. Keep characterization tests green; flag any model whose data is stubbed.`
- `Proceed to Phase 4.`
- `Proceed to Phase 5. Show me one real backtest on a Nifty 100 universe with gross vs net returns.`
- `Proceed to Phase 6.`
- `Proceed to Phase 7. Default to Ollama for development; keep the provider switchable.`
- `Proceed to Phase 8. Give me screenshots or a description of each page when done.`
- `Proceed to Phase 9.`
- `Proceed to Phase 10.`

## If Claude Code drifts

Paste this reminder: `Re-read docs/CHANGES.md and the Non-negotiable rules in my master prompt. Point out which rule your last change may violate and fix it before continuing.`
