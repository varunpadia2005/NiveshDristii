# NiveshDristi — Change Plan
### Learning from `virattt/ai-hedge-fund` · India (NSE/BSE) first · Global-ready by design

> Educational / research use. Not investment advice. See Section 11 on SEBI rules before showing outputs to anyone else.

---

## 0. What this is based on (read this first)

- **Read:** the repo's README, `ROADMAP.md` and `VISION.md` (as of 22 Oct 2026). These describe the *architecture* of the current v2 engine.
- **Not read:** the source files inside `hedge_fund/`. GitHub blocked automated access to the folder tree. So this plan borrows **design ideas**, not code, and makes no claims about specific functions or file names inside that repo.
- **Not seen:** your actual NiveshDristi code (`D:\NiveshDristi`). From your earlier description it has: TA (RSI, MACD, Bollinger, MAs), fundamental guardrails (P/E, ROE, D/E), sector rotation, price-range engines, backtesting, yfinance + pandas-ta + Plotly + Streamlit, and a weak frontend. **Phase 0 of the Claude Code prompt audits your real code first** and corrects anything here that doesn't match.

---

## 1. The 12 changes that matter most

| # | Change | Why |
|---|---|---|
| 1 | Introduce one contract: `AlphaModel.predict() -> Signal(conviction ∈ [-1,+1], thesis, evidence)` | Turns your separate RSI / MACD / fundamentals / sector modules into interchangeable, backtestable, blendable analysts |
| 2 | Add a `MarketProfile` abstraction (exchange, calendar, currency, costs, tick rules, benchmark, sector taxonomy) | This is the single thing that makes "India now, global later" cheap instead of a rewrite |
| 3 | Add a pluggable `DataClient` protocol; yfinance becomes *one* provider, not the foundation | yfinance is fine for prototyping but is unofficial and can break or return gaps; you need fallbacks and caching |
| 4 | **Point-in-time data discipline** (use result *announcement* dates, not period-end dates) | Without it, your backtests silently use information that wasn't public yet |
| 5 | One engine verb `advance` shared by backtest and paper modes; decide at close of T, execute at T+1 | "What you backtest is what you paper-trade" — no divergence |
| 6 | India-realistic execution: costs, taxes, circuit limits, T+1 settlement, **long-only cash-segment default** | The US repo assumes shorting is easy. For Indian retail cash equities it largely isn't |
| 7 | Deterministic risk gates that no model or LLM can override | Position, sector, liquidity, exclusion-list caps |
| 8 | LLMs form *views and narrate*; code sizes positions | Keeps GenAI useful without letting it touch the trade |
| 9 | Hash-chained, append-only paper ledger + kill switch + idempotent `tick` | Gives you an honest, tamper-evident track record |
| 10 | Validation gate (walk-forward, deflated Sharpe, PBO) before any strategy is trusted | Stops you fooling yourself with overfit backtests |
| 11 | India-specific alpha models (promoter pledge, delivery %, FII/DII, India VIX regime, results-drift) | This is where an Indian product can differ from a US clone |
| 12 | UI becomes a thin client over the engine (Streamlit multipage now; API later) | Fixes the "weak frontend" without coupling logic to the UI |

---

## 2. What the reference repo is today (summary)

- A **fund as a persistent object**: mandate, analysts, capital, books.
- **One verb, `advance`**: reconcile → execute last decision → mark to market → assess next decision → record. Same code in backtest and paper mode; live is a broker plug-in away.
- **Three nested layers:** Fund = allocator over Strategies; Strategy = policy over Analysts; Analyst = alpha model → Signal.
- **Two analyst flavours** behind the same interface: LLM investor personas and quant models (e.g. post-earnings drift; momentum, mean reversion, regimes still planned).
- **Hash-chained ledger** of session records, a kill switch, idempotent `paper tick`, event log.
- **Stated principles:** point-in-time honesty; backtest = live system; the LLM never touches the trade; self-improvement is gated by validation (CPCV/PBO); paper before real.
- **Interfaces:** terminal app (Textual) as main UI, a thin CLI with JSON output, a web dashboard scaffold.
- **Data:** a US-centric paid data API (Financial Datasets). Not usable for NSE/BSE as-is.

---

## 3. Concept mapping: reference repo → NiveshDristi

| Reference concept | NiveshDristi equivalent | Change needed |
|---|---|---|
| `AlphaModel` / `Signal` | `nd.alpha.base.AlphaModel`, `Signal` | New; wrap every existing engine |
| Quant models (PEAD, momentum…) | TA ensemble, momentum, mean-reversion, quality/value, results-drift, regime | Port + add |
| LLM investor agents | India-flavoured personas + a neutral "Analyst Narrator" | New |
| Strategy (pod) | `StrategySpec` YAML: models + blend policy + capital slice | New |
| Portfolio construction | Conviction-weighted, long-only, capped | New |
| Risk model | `RiskGate` chain | New |
| Broker protocol | `SimBroker`, `PaperBroker` (live = out of scope) | New |
| `DataClient` | `DataClient` + `YFinanceClient`, `NseBhavcopyClient`, … | Refactor |
| Mandates carry no tickers | `mandates/*.yaml` + `universes/*.yaml` | New |
| Ledger + kill switch | `nd.ledger`, `nd.paper` | New |
| Validation gate | `nd.validation` | New |
| TUI / CLI / dashboard | Streamlit multipage + `nd` CLI | Rebuild frontend |

---

## 4. Detailed changes

Each item: **What → India specifics → Global hook → Done when**.

### C1. Core domain types
- **What:** `Instrument(symbol, exchange, market_id, currency, isin, sector)`, `Signal`, `AlphaModel`, `Decision`, `Order`, `Fill`, `SessionRecord`. Pydantic v2 models, frozen/immutable where possible.
- **India:** symbols normalised internally as `RELIANCE.NSE`; provider-specific suffixes (`.NS`, `.BO`) live only inside provider adapters. Use ISIN as the stable key across symbol changes and mergers.
- **Global hook:** nothing in `core/` may mention "NSE", "₹", "IST" or "Nifty". Those live in `markets/in_nse/`.
- **Done when:** a test fails if any file under `core/` imports from `markets/` or contains India-specific literals.

### C2. `MarketProfile` (the global-readiness seam)
- **What:** a registry of market definitions with: timezone, session hours, holiday calendar, currency, lot/tick conventions, settlement cycle, price-limit rules, cost model, tax model, benchmark index, sector taxonomy, shorting allowed (bool), default universe.
- **India (`IN_NSE`):** IST; regular session 09:15–15:30; T+1 settlement; price bands/circuits; shorting in cash segment = **False** (default long-only); benchmark Nifty 50 / Nifty 500 (prefer **TRI**, total return index, over price index); sector taxonomy aligned to NSE sector indices.
- **Global hook:** adding `US_NYSE` later = adding one profile + one data adapter + one cost model, no engine edits.
- **Done when:** the engine takes `market_id` as an argument and a toy second profile (even a fake one) runs the backtest end-to-end.

### C3. Data layer
- **What:** `DataClient` protocol (`prices`, `fundamentals`, `corporate_actions`, `index_constituents`, `flows`, `filings`), a provider chain with fallback order, a local cache (Parquet or DuckDB), data-quality checks (gaps, zero volume, stale bars, split discontinuities), rate-limit and retry handling.
- **India sources to wire (verify terms of use and availability for each before relying on it):**
  - Prices: yfinance (`.NS`, `.BO`; indices like `^NSEI`, `^NSEBANK`, `^INDIAVIX`) as fallback; NSE bhavcopy (EOD, includes delivery quantity) via `jugaad-data` or `nsepython`-style libraries as primary EOD; niftyindices.com for official index history incl. TRI.
  - Corporate actions: splits, bonuses, dividends, rights, mergers. Store raw + adjusted prices separately.
  - Fundamentals: quarterly/annual statements with **announcement date** and the exchange filing timestamp where possible.
  - Shareholding pattern (quarterly): promoter %, promoter pledge %, FII/DII/public.
  - Flows: daily FII/DII cash-market flows; bulk/block deals; insider (PIT/SAST) disclosures.
  - Macro: RBI repo rate, CPI, INR/USD, crude, 10Y G-sec (later: FRED/World Bank for global).
  - Avoid scraping sites whose terms forbid it (several popular Indian screener sites do). Prefer exchange disclosures and licensed APIs.
- **Global hook:** provider registry keyed by `market_id`; same `DataClient` for any country.
- **Done when:** a single call `data.prices("RELIANCE.NSE", start, end)` works via at least two providers, with cache hits on the second call and a failing primary falling back automatically.

### C4. Point-in-time correctness
- **What:** every fundamental record carries `period_end`, `announced_at`, `source`. Queries take `as_of` and return only rows with `announced_at <= as_of`. Index constituents are as-of too (avoid survivorship bias: use the Nifty 500 *as it was*, including delisted names where available).
- **India:** SEBI listing rules require quarterly results within 45 days of quarter end (60 days for the annual/Q4 case) — so period-end + 0 days is never a safe availability date. Use the announcement timestamp; if you can only get period-end, add a conservative lag (e.g. 60 days) and flag results as "approximate PIT".
- **Done when:** a test proves that on a given historical date the system cannot see a result announced the next day.

### C5. Engine: `advance`
- **What:** one session = reconcile → execute pending decision (at T+1 close or open — pick one and document it) → mark → assess (on rebalance days) → record. Backtest loops it over history; paper calls it once per completed session.
- **India:** use NSE trading calendar for sessions; Muhurat (Diwali) special sessions and special Saturday sessions are edge cases — config flag to include/exclude.
- **Done when:** replaying a paper fund over a past period produces records identical to the backtest for the same period (the "byte-for-byte" property).

### C6. Execution realism for India
- **Costs (all in `markets/in_nse/costs.yaml`, never hard-coded; rates change, verify current values):** brokerage (flat or %), STT on delivery (both sides), exchange transaction charges, SEBI turnover fee, stamp duty (buy side), GST on brokerage + charges, depository (DP) charge per scrip on sells. Slippage model scaled by liquidity.
- **Taxes (`tax.yaml`, optional module):** short-term vs long-term capital gains on listed equity with holding-period logic (12-month threshold), exemption threshold, and an FY-aware loss set-off. Rates and thresholds have changed in recent budgets — keep configurable and verify against the latest Finance Act before use.
- **Market rules:** price bands (circuit limits) — an order on a stock locked at its limit may not fill; exclude stocks under surveillance measures (ASM/GSM lists) and illiquid/ill-priced names by default; ADV cap (e.g. never exceed a small % of average daily traded value); minimum market cap and price filters; integer share quantities; settlement on T+1.
- **Shorting:** default **long-only**. A sleeve that needs shorts must be expressed via F&O and is a *later* module with lot sizes, margin and expiry logic. Do not port the reference repo's market-neutral sleeves into v1.
- **Done when:** the backtest reports gross and net-of-cost returns separately, and a test shows a high-turnover strategy loses materially after costs.

### C7. Portfolio construction + risk gates
- **What:** conviction → target weights (long-only, conviction-weighted, with optional vol scaling) → `RiskGate` chain that clamps: max position %, max sector %, min cash, ADV/liquidity cap, turnover limit, exclusion lists (ASM/GSM, F&O ban if relevant, user blacklist), drawdown circuit (reduce risk after X% drawdown).
- **Rule:** gates are plain Python. No model or LLM output can bypass them. Log every clamp with the reason.
- **Done when:** a unit test feeds an extreme-conviction signal on an illiquid stock and shows the order is clipped with a logged reason.

### C8. Alpha models: port existing + add new
**Port (each becomes an `AlphaModel` returning conviction + thesis + evidence numbers):**
1. TA ensemble (RSI, MACD, Bollinger, MA cross) — with *regime-aware* weighting rather than fixed rules.
2. Fundamental guardrails (P/E, ROE, D/E) — convert from hard pass/fail filters into a quality score **plus** a hard exclusion list for extreme cases.
3. Sector rotation — relative strength of NSE sector indices vs Nifty, with momentum and breadth; emits a sector tilt that other models can read.
4. Price-range engine — support/resistance and ATR-based ranges as a *risk/entry-zone* input, not a standalone signal.

**Add (quant):** time-series & cross-sectional momentum, mean reversion, value/quality factors (earnings yield, ROCE, margin stability, cash conversion), low-volatility, earnings-reaction drift on Indian quarterly results, market-regime detection (HMM or simple vol/trend states on Nifty + India VIX).

**Add (India-specific):**
- Promoter holding trend and **pledge** change (rising pledge = red flag).
- Delivery-percentage anomalies from bhavcopy.
- FII/DII flow regime.
- Bulk/block deal and insider-trade signals.
- India VIX regime / PCR and open-interest context for index-level risk.
- Earnings-quality flags: CFO vs PAT, receivable-days drift, auditor changes, related-party notes (these can feed an LLM reader).
- Macro overlay: repo-rate direction, INR, crude (sector sensitivities: banks, IT exporters, OMCs, paints, etc.).

**Done when:** every model has a unit test with fixture data, a documented `signal_horizon`, and appears in a model registry listing.

### C9. LLM layer (GenAI, kept safe)
- **What:** `make_llm(provider, model)` factory (Anthropic, OpenAI, Google, and **Ollama** for a free local path), structured outputs validated with Pydantic, retries, token/cost logging, response caching keyed by (prompt hash, data hash).
- **Personas (stylised approximations of public philosophies, not endorsements; include the disclaimer in every output):** a Jhunjhunwala-style "India growth + conviction" lens; a QGLP lens (Quality, Growth, Longevity, Price); a "SMILE" small-cap lens (Small, Medium experience, Large aspiration, Extra-large market potential); a Graham-style deep-value lens; a risk-skeptic lens that argues *against* the trade. Plus a neutral **Analyst Narrator** that explains the deterministic signals in plain English.
- **Grounding rule:** all numbers are injected from tables by code; the LLM may not introduce figures. Output must cite which evidence fields it used. Reject outputs that reference numbers not in the evidence packet.
- **Filings/concalls RAG (later phase):** annual report, results PDFs, concall transcripts → chunk + embed → retrieval for the thesis. Always show source snippets.
- **Done when:** with the LLM mocked, the pipeline runs deterministically in tests; with a real model, the same inputs produce schema-valid signals; and a "lying LLM" test (injects a fake number) is rejected.

### C10. Backtesting + validation gate
- **What:** backtest via `advance`; metrics (CAGR, vol, Sharpe, Sortino, max drawdown, turnover, hit rate, exposure, cost drag), benchmark comparison against Nifty TRI, walk-forward evaluation, parameter-sensitivity plots, **deflated Sharpe / PBO / CPCV** when many variants are tried, regime breakdown (bull/bear/sideways, e.g. 2020 crash, 2022 drawdown).
- **Rule:** a strategy is "promotable" only if it passes the gate; the UI shows the gate result next to every equity curve.
- **Done when:** an intentionally overfit toy strategy is flagged by the gate.

### C11. Paper fund, ledger, scheduler, observability
- **What:** append-only `SessionRecord`s hash-chained (each stores previous hash); replay verifies chain and rebuilds state; broker book reconciled against ledger before each tick; kill switch (any exception inside a tick halts the fund); idempotent `nd paper tick` safe to call from Windows Task Scheduler / cron; `events.jsonl`; optional Telegram/email notification and a heartbeat.
- **India:** tick runs after NSE close once EOD data is published (not at 15:30 sharp); skip holidays using the market calendar.
- **Done when:** running `tick` twice for the same session changes nothing; corrupting one ledger line makes verification fail loudly.

### C12. Frontend (fix the weak UI)
- **What:** keep Streamlit, but make it a **thin client** that calls the same service layer as the CLI. Multipage layout:
  1. **Market Overview** — Nifty/Bank Nifty, India VIX, sector heatmap, FII/DII flows, regime badge.
  2. **Stock Deep-Dive** — price + indicators (Plotly), fundamentals card, each analyst's signal + thesis, risk-gate verdicts, entry/stop zones.
  3. **Signals Board** — universe-wide table, filter by sector/conviction/liquidity, "why" drawer.
  4. **Backtest Lab** — choose mandate + universe + dates; equity vs benchmark; costs; validation-gate result.
  5. **Paper Fund** — NAV, positions, decisions with theses, ledger verification status, halt/resume.
  6. **Settings** — LLM provider/model, data providers, market profile, costs.
- **UX rules:** cache expensive calls (`st.cache_data`), never recompute on every widget change, show data "as of" timestamps, always show the disclaimer, dark/light safe colours, loading states, no blocking LLM calls on page load.
- **Later:** FastAPI service in front of the engine + a richer web client; the engine API is already UI-agnostic.

### C13. Packaging, config, quality
- `pyproject.toml` with `uv` or Poetry; `src/niveshdristi/` layout; `ruff`, `mypy` (or pyright), `pytest`; pre-commit; CI that runs tests offline using fixtures (no live network in tests).
- Config precedence: env vars > user config file > defaults. Secrets in `.env`, never committed.
- **Windows-friendly:** use `pathlib`, avoid Makefile-only workflows, test file locking and path handling on Windows.
- CLI `nd` with JSON output mode (`nd backtest`, `nd paper create|tick|status|halt|resume`, `nd data fetch`, `nd signals`).

### C14. Global expansion path (design now, build later)
1. Phase A (now): everything India, but behind `MarketProfile`.
2. Phase B: add `US` profile as a proof (data via a US provider, USD, US calendar, different cost model, shorting allowed flag).
3. Phase C: multi-market universes, FX conversion layer (base currency for NAV), cross-market benchmark, per-market sector taxonomies mapped to GICS.
4. Phase D: more markets (UK, Japan, SGX, etc.) as profile + adapter packs.
- **Guardrail:** a CI test greps `core/` and `engine/` for market-specific literals and fails the build if any appear.

---

## 5. Target folder structure

```
niveshdristi/
├─ pyproject.toml
├─ src/niveshdristi/
│  ├─ core/            # types, Signal, AlphaModel, Decision, errors (market-agnostic)
│  ├─ markets/
│  │  ├─ registry.py
│  │  ├─ in_nse/       # profile.py, calendar.py, costs.yaml, tax.yaml, sectors.yaml, rules.py
│  │  └─ us_nyse/      # added in Phase 9 as proof
│  ├─ data/
│  │  ├─ client.py     # DataClient protocol
│  │  ├─ providers/    # yfinance.py, nse_bhavcopy.py, niftyindices.py, ...
│  │  ├─ cache.py  quality.py  pit.py  corporate_actions.py
│  ├─ alpha/
│  │  ├─ quant/        # ta_ensemble, momentum, mean_reversion, quality_value, results_drift, regime
│  │  ├─ india/        # promoter_pledge, delivery_pct, fii_dii, bulk_block, macro_overlay
│  │  ├─ sector_rotation.py  price_range.py  fundamental_guardrails.py
│  │  └─ llm/          # personas, narrator, grounding_validator
│  ├─ portfolio/       # construction.py, risk_gates.py, allocator.py
│  ├─ execution/       # broker.py (protocol), sim_broker.py, paper_broker.py, costs.py, tax.py
│  ├─ engine/          # advance.py, backtest.py, metrics.py
│  ├─ validation/      # walk_forward.py, deflated_sharpe.py, pbo.py
│  ├─ ledger/          # session_record.py, chain.py, replay.py
│  ├─ paper/           # fund.py, tick.py, kill_switch.py, events.py, notify.py
│  ├─ llm/             # make_llm.py, providers/, cache.py, schemas.py
│  ├─ services/        # thin facade used by CLI and UI
│  ├─ cli/             # `nd`
│  └─ ui/              # streamlit app + pages
├─ mandates/  universes/  strategies/       # YAML (mandates carry no tickers)
├─ tests/  fixtures/
└─ docs/  (AUDIT.md, ARCHITECTURE.md, CHANGES.md, DISCLAIMER.md)
```

---

## 6. Core interface sketches (shape, not final code)

```python
# core/signal.py
class Signal(BaseModel, frozen=True):
    instrument: Instrument
    as_of: datetime               # point-in-time stamp
    conviction: float             # [-1, +1]; long-only markets clamp negatives to 0 at construction
    horizon_days: int
    thesis: str                   # plain-English explanation
    evidence: dict[str, float|str]# the numbers the thesis relies on
    model_id: str

# core/alpha.py
class AlphaModel(Protocol):
    id: str
    def predict(self, ctx: "AsOfContext") -> list[Signal]: ...

# core/market.py
class MarketProfile(BaseModel):
    market_id: str; timezone: str; currency: str
    session_open: time; session_close: time
    settlement_days: int; shorting_allowed: bool
    calendar: TradingCalendar; costs: CostModel; tax: TaxModel | None
    benchmark: str; sector_taxonomy: dict[str, str]

# data/client.py
class DataClient(Protocol):
    def prices(self, inst, start, end, *, as_of=None) -> pd.DataFrame: ...
    def fundamentals(self, inst, *, as_of) -> pd.DataFrame: ...   # has announced_at
    def corporate_actions(self, inst, start, end) -> pd.DataFrame: ...
```

---

## 7. India market rule sheet (verify every value; keep in config files)

| Item | Default in config | Note |
|---|---|---|
| Session | 09:15–15:30 IST, pre-open ~09:00–09:15 | Confirm against current NSE circulars |
| Settlement | T+1 | |
| Shorting (cash, delivery) | Not allowed for retail | Intraday only; otherwise via F&O |
| Price bands | Per-stock bands (e.g. 2/5/10/20%) | Many F&O stocks have dynamic bands; fetch per-symbol when possible |
| STT (delivery) | Charged on buy and sell | Rate and rules change; read current schedule |
| Stamp duty | Buy side, uniform rate | |
| Capital gains (listed equity) | Short-term vs long-term, 12-month threshold, annual exemption | Rates changed in 2024 and may change again; verify latest Finance Act |
| Results timeline | Quarterly within 45 days; annual within 60 days | Basis for PIT lags |
| Lot sizes (F&O) | N/A in v1 | Revised periodically; later module |
| Holidays | Maintain `holidays_in.yaml`; verify any library's NSE calendar coverage | Add Muhurat session flag |

---

## 8. What NOT to copy from the reference repo

- The US-only data provider and USD/US-calendar assumptions.
- Market-neutral long/short sleeves (shorting isn't a retail cash-equity default in India).
- The "famous investor in a prompt" pattern *without* grounding and validation. Keep it, but force evidence-citation.
- The v1/v2 split and the Textual TUI. Your UI is Streamlit; don't rebuild a TUI.
- Code verbatim. The repo is MIT-licensed, so reuse is legal with attribution, but re-implementing the ideas to fit your types and market abstraction will be cleaner. If you do copy any file, keep the licence notice.

---

## 9. Phased roadmap (indicative, matches the Claude Code prompt)

| Phase | Output | Rough effort |
|---|---|---|
| P0 | Audit of current code, safety-net tests, branch, `docs/AUDIT.md` | 0.5–1 day |
| P1 | Core types, `MarketProfile` (IN_NSE), config, packaging, CLI skeleton | 2 days |
| P2 | Data layer, cache, calendar, corporate actions, PIT store, quality checks | 3–4 days |
| P3 | Port existing modules to `AlphaModel`; add quant + India models | 4–6 days |
| P4 | Portfolio construction, risk gates, India costs/tax, sim broker | 3 days |
| P5 | `advance` engine, backtest, metrics, validation gate, reports | 3–4 days |
| P6 | Paper fund, ledger, kill switch, tick, scheduler, events, notifications | 3 days |
| P7 | LLM layer, personas, narrator, grounding validator, eval fixtures | 3–4 days |
| P8 | Streamlit multipage UI + CLI polish | 3–4 days |
| P9 | US profile proof of global readiness; FX/base-currency groundwork | 2–3 days |
| P10 | Hardening: docs, CI, disclaimers, performance, packaging | 2 days |

---

## 10. Risks and open questions

- **Data quality is the real bottleneck.** Free Indian data is patchy (corporate actions, delisted names, historical shareholding). Budget time for validation and consider a licensed provider once the engine is proven.
- **Backtest honesty:** survivorship bias, look-ahead on fundamentals and adjusted prices are the usual killers. The PIT tests in C4 matter more than any model.
- **LLM cost/latency:** cache aggressively; run LLM analysts only on shortlisted names; use a local model (Ollama) for development.
- **Overfitting:** the more models and parameters you try, the more the validation gate matters.
- **Scope creep:** F&O, intraday, live broker integration and alt-data are deliberately out of v1.

---

## 11. Compliance note (relevant to your NISM XV work)

In India, giving investment recommendations to others for a fee, or holding yourself out as a research analyst or investment adviser, falls under SEBI's Research Analyst and Investment Adviser regulations and requires registration. Keep NiveshDristi as a personal/educational tool, show the disclaimer on every screen and report, and don't distribute its outputs to third parties as recommendations without checking the current SEBI rules. Retail algorithmic trading through broker APIs also has its own SEBI/exchange framework that has been evolving, so treat live trading as out of scope and re-check the rules if you ever consider it.

---

## 12. Definition of done (v1, India)

1. `nd backtest mandates/core.yaml --universe nifty100 --start 2018-01-01` runs offline from cache and prints net-of-cost results vs Nifty TRI with a validation-gate verdict.
2. `nd paper create/tick/status/halt/resume` works, is idempotent, and the ledger verifies.
3. Every existing NiveshDristi analytic is an `AlphaModel`; at least 5 new ones exist, 3 of them India-specific.
4. LLM narrator produces grounded, schema-valid theses; the lying-LLM test passes.
5. Streamlit app has the six pages, with as-of stamps and disclaimers.
6. `US` profile smoke test passes with zero edits to `core/` and `engine/`.
7. CI green, with no network calls in tests.
