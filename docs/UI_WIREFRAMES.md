# UI Wireframes (NEW, P8-S2) — text wireframes for approval

Layout constants for EVERY page (top-to-bottom):
1. BANNER STRIP (one shared component, non-droppable):
   [DATA LIMITATIONS: <codes from the ledger/report>] — always, from data
   [RATES UNVERIFIED] — always while rates_verified is False
   [Educational disclaimer — verbatim first bold line of docs/DISCLAIMER.md]
2. PAGE BODY (below).
3. FOOTER STRIP: `as-of: <last data session | report as-of | created date>`
   (NEVER the system clock) + market labels from the profile (ISO currency
   code, no symbols) + `[UNTRUSTED display text]` tag wherever LLM-derived
   text appears (never adjacent to a control).

Navigation (sidebar, single column, mobile-collapsible):

```
┌ sidebar ─────────────┐  ┌ main ────────────────────────────────────────┐
│ NiveshDristi         │  │ BANNER STRIP                                 │
│ ▸ Overview           │  │ ──────────────────────────────────────────── │
│ ▸ Deep-Dive          │  │ PAGE BODY                                    │
│ ▸ Signals            │  │                                              │
│ ▸ Backtest Lab       │  │                                              │
│ ▸ Paper Fund  ●      │  │                                              │
│ ▸ Settings           │  │ footer: as-of … | INR | market | [UNTRUSTED] │
│ fund: [id] base: […] │  └──────────────────────────────────────────────┘
└──────────────────────┘
```

## 1. Overview
```
│ BANNER STRIP                                                  │
│ Regime badge [from validation/report when available]          │
│ ┌ unavailable: no verified data source ─────────────────────┐ │
│ │ benchmark · Bank Nifty · India VIX · sector heatmap ·     │ │
│ │ FII/DII flows — panels render "unavailable" until a       │ │
│ │ verified data source is configured                        │ │
│ └───────────────────────────────────────────────────────────┘ │
│ footer                                                        │
```

## 2. Deep-Dive
```
│ BANNER STRIP                                                  │
│ ticker selector (from universe via services)                  │
│ [price + indicators chart — Plotly, when data available]      │
│ [fundamentals card | unavailable: no verified data source]    │
│ [analyst signals + theses (quant models; LLM text only as     │
│  UNTRUSTED display text away from controls)]                  │
│ [risk-gate verdicts | entry/stop zones — unavailable panel]   │
│ footer                                                        │
```

## 3. Signals
```
│ BANNER STRIP                                                  │
│ filters: sector ▾ conviction ▾ liquidity ▾                    │
│ table: symbol | conviction | thesis (truncated)               │
│   └ "why" drawer (expander): full thesis, evidence ids        │
│ footer                                                        │
```

## 4. Backtest Lab
```
│ BANNER STRIP                                                  │
│ form: mandate ▾ universe ▾ start ▾ end   [Run]                │
│ [equity vs benchmark — Plotly]   [costs table]                │
│ [validation-gate verdict + banners]                           │
│ footer                                                        │
```

## 5. Paper Fund (P8-S3 scope — fully built)
```
│ BANNER STRIP                                                  │
│ ┌ fund header ──────────────────────────────────────────────┐ │
│ │ fund_id · records N · verify: verified|FAILED (loud)      │ │
│ │ cash · positions table (symbol, shares, market value)     │ │
│ │ halted: YES/NO (+ reason)                                 │ │
│ └───────────────────────────────────────────────────────────┘ │
│ ┌ decisions & theses ───────────────────────────────────────┐ │
│ │ from the R9b sidecar when present; label "unverified"     │ │
│ │ when the content hash fails; "decisions not recorded"     │ │
│ │ otherwise. Gate log reasons listed as display text.       │ │
│ └───────────────────────────────────────────────────────────┘ │
│ [halt] [resume] — ONLY when the write-actions config flag is  │
│ ON; each behind an explicit confirm checkbox; executed via    │
│ the same functions the CLI uses. OFF by default.              │
│ footer (as-of from the last ledger session, never the clock)  │
```

## 6. Settings
```
│ BANNER STRIP                                                  │
│ LLM provider/model (registry names; VERIFY note)              │
│ data providers (names only) · market profile labels           │
│ costs (read-only view of config values)                       │
│ API keys: PRESENCE ONLY (●●● set / not set) — never values    │
│ footer                                                        │
```

UX principles: st.cache_data with explicit keys including the as-of date
and ledger hash; no recompute on widget change; loading/empty/error states
on every panel; no blocking LLM calls on page load; readable in light and
dark themes; no color-only meaning (text labels accompany every status);
keyboard navigable (native widgets only).

---

# AS BUILT (P8-S5..S9)

All six pages exist; every page renders the shared banner strip + footer
(as-of from data) and NO unsafe HTML:

- **Overview** — KPI ribbon (fund value at last close, last-session net and
  gross P&L separately), direction legend, positions (symbol, lean pill,
  uncalibrated conviction, unrealised %, "Why?" expander with thesis and
  horizon), sector/benchmark panel = unavailable, "What changed in the last
  session" feed (ticks/quality/halt/resume/recover events), "Needs
  attention" list (verify failure, halt, UNVERIFIED sidecar, limitation
  count).
- **Market Overview** — "Last data session" badge (never Open/Closed) with
  the holiday-calendar note; regime/benchmark/VIX/heatmap/flows = honest
  unavailable panels (the regime model needs aux frames snapshots lack).
- **Signals** — board rows for every stored instrument: icon+word lean,
  conviction (uncalibrated, -1 to +1), horizon, data_status, liquidity
  (snapshot volume); conviction slider filter; type-ahead search; sector
  filter displayed as unavailable; "Why?" expanders (inert text).
- **Deep-Dive** — plotly candlestick + RSI/MACD/50-200-day text panes from
  the TA wrapper's indicator frame; entry/stop zones from the price-range
  evidence function labelled evidence-only; per-model leans; recorded gate
  verdicts from the sidecar clamp log (never recomputed);
  guardrails/fundamentals = unavailable. Compare view side-by-side, no
  action buttons.
- **Backtest Lab** — Run button executes the engine over stored snapshots
  (live bundle minus the legacy TA scorer — warmup impossibility
  documented); verdict FIXED: "pipeline demonstration only; not evidence
  of performance"; promotable shown always-False; gross vs net chart; drag
  split into fees/slippage; TrialRecorder summary = unavailable panel.
- **Paper Fund** — header chips (verify verified/FAILED, halt state),
  positions table, decisions panel (verified / UNVERIFIED / not recorded),
  optional detail view: paginated records, session drill-down (fills,
  costs, recorded clamp log), events panel, flag-gated halt with
  confirmation (off by default).
- **Settings** — read-only: market labels from the profile, provider/model
  names (env-documented, VERIFY note), key PRESENCE only (never values),
  data-source status table.
