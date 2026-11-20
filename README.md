# NiveshDristi (निवेश दृष्टि)

**Investment Vision** — an AI-assisted portfolio-RESEARCH tool for Indian
equities. Educational, personal-use, offline-first.

## What this is — and what it is NOT (read first)

> **NiveshDristi is an educational research tool.** It is NOT investment
> advice and it is NOT a trading system. Everything is tested on synthetic
> data; its only live data path is one unofficial feed (yfinance) whose
> terms you must accept yourself. All cost and tax rates are UNVERIFIED
> placeholders — every number the tool shows about real costs is a
> hypothesis. The paper fund, ledger, and validation gate are honest
> bookkeeping of a simulation, not a record of real money. US-market
> support is an architecture proof only: no US data source, rates,
> holidays, or benchmarks are provided. Never fund it, never connect it to
> a broker, and never treat any of its output as a recommendation.

Five principles: honesty over hype · no look-ahead, ever · everything
explainable · engine computes, LLM narrates · every feature testable.

## Quickstart (Windows first, ~10 minutes)

```powershell
git clone https://github.com/varunpadia2005/NiveshDristii.git
cd NiveshDristii
git checkout rebuild/v2
py -3.13 -m venv "D:\venvs\niveshdristi"
& "D:\venvs\niveshdristi\Scripts\pip" install -e ".[dev]"

# legacy fixtures (one-time; the characterization tests need them)
& "D:\venvs\niveshdristi\Scripts\python" tests\create_fixtures.py

# a SYNTHETIC demo paper fund (no network; 130+ sessions, fills, sidecars)
& "D:\venvs\niveshdristi\Scripts\python" tools\make_demo_fund.py --base "D:\Nivesh Dristi\demo_funds" --tamper-ledger --tamper-sidecar

# the UI (binds 127.0.0.1 only; usage stats off)
$env:NDR_FUND_BASE = "D:\Nivesh Dristi\demo_funds"
$env:NDR_FUND_ID   = "demo_synthetic"
& "D:\venvs\niveshdristi\Scripts\python" -m streamlit run src\niveshdristi\ui\app.py
```

What you should see: the DataLimitations banner, a RATES UNVERIFIED banner,
the educational disclaimer on every page, and honest per-page states —
including "unavailable: no verified data source" panels. Full walkthrough:
docs/UI_MANUAL_CHECKLIST.md.

## The offline gate (the heart of the project)

```
& "D:\venvs\niveshdristi\Scripts\python" tools\phase1_gate.py --phase0 <phase0-worktree>
```
18+ named checks (G01–G19): clean-tree, legacy contract, literal guard,
ruff/mypy on new paths, the offline suite, zero-write proof, and the
legacy-equality comparison against the frozen Phase-0 snapshot. See
docs/CI.md and docs/RESTORE.md.

## Command surface

`nd --help` — validate, config, models, paper (create/tick/status/verify/
replay/explain/...), backtest run (offline over stored snapshots).
`nd data fetch TICKERS --start --end` and `nd data refresh --universe
--start --end` fetch daily prices through the market's data provider and
print a report-only JSON summary (nothing is stored; US_NYSE refuses
with a typed error — no verified US source). `nd signals generate TICKER
--as-of` runs the live model bundle over fetched prices and prints the
per-model signals and blended convictions.

## Docs

| Doc | What it covers |
|---|---|
| docs/VERIFY.md | what is verified vs UNVERIFIED (data sources, rates, models) |
| docs/PROGRESS.md | phase-by-phase build history from raw outputs |
| docs/RESTORE.md | rebuild everything on a new machine |
| docs/CI.md | the GitHub Actions workflow |
| docs/SCHEDULER.md | Windows Task Scheduler for the paper tick |
| docs/UI_WIREFRAMES.md, docs/UI_MANUAL_CHECKLIST.md | the UI |
| docs/DISCLAIMER.md | the educational-use disclaimer (shown in every UI page) |
| docs/UI_REACT_TRACK.md | the future Next.js/FastAPI client (deferred) |

## Status

Phase 10 (hardening). CI: GitHub Actions (see docs/CI.md; fill the three
action SHAs before the first push). Known blocked items: official 2026 NSE
holiday list, verified fee/tax rates, TRI benchmark, constituents,
announcement-dated fundamentals — see docs/VERIFY.md.
