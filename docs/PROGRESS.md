# Phase 1 Progress Report

Rewritten 2026-10-24 from verified command output of the takeover session. Every
number below was produced by a command in this session; nothing is carried over
from earlier claims.

## Environment actually used

- Python **3.13.7** (the global interpreter, `C:\Users\HP\AppData\Local\Programs\Python\Python313\python.exe`).
- pytest **9.1.1**, pydantic **2.13.5**, typer **0.27.3**, mypy **2.4.0** (gate G17 output).
- `.venv-test` in the repo root is a partial leftover venv: it has **no pytest, no
  pydantic, no typer** and is NOT used. Do not trust earlier claims of "pytest 8.3.4".
- Python 3.11 is **not installed** on this machine (`py --list` shows only 3.13), so the
  planned 3.11 verification run was skipped. The 3.11 pin decision is deferred to the
  start of Phase 2; `pyproject.toml` still says `requires-python >= 3.11`.

## Test results (at Phase 1 close)

```
$ python -m pytest -v -p no:cacheprovider
collected 114 items
113 passed, 1 xfailed, 2 warnings in ~5-7s
```

- 0 failed, 0 errors, 0 skipped, exactly **1 xfailed** — the approved strict xfail
  `test_holidays_yaml_covers_current_year` ("Phase 2: fill 2026 holidays from the NSE
  official list"). It is the only xfail in the suite (gate G15).
- The 2 warnings are the known universe-count warnings (nifty50=49, nifty100=101).

## Gate (tools/phase1_gate.py)

`python tools/phase1_gate.py --phase0 "D:\Nivesh Dristi\phase0_wt"` → `GATE: PASS` (exit 0).

Design as of commit `5e5f43b`..`cdbba61`:

- **One shared pytest run** (`pytest runs: 1`, `-v -p no:cacheprovider`). G01 (clean
  status before/after), G06 (counts + node IDs) and G07 (utcnow) all consume that run.
- **G03b precheck**: `phase0_wt/tools/dump_config.py` and `compare_backtest.py` must
  exist and md5-match the repo copies before G04/G05 run; the gate never writes to the
  worktree.
- **G18 zero-writes**: an eager sha256 snapshot of every file under the repo root
  (excluding only `.git` and `.venv*`) is taken before any subprocess runs; at gate end
  any file newer than the start marker must be byte-identical to its snapshot (reported
  as `INFO G18 rewritten identically`) or the gate FAILs; new and deleted files FAIL.
  *Legacy tests rewrite three gitignored parquet fixtures (`tests/fixtures/*.parquet`,
  "Save for reference" writes in `tests/test_characterization.py`) on every pytest run;
  they are byte-identical between runs and appear as INFO. On a **fresh clone** those
  files do not exist at start, so the FIRST gate run FAILs G18 once; from the second
  run on it passes. No allowlist exists for this.*
- G06 additionally requires **every collected node ID to start with `tests/`** (derived
  from the same `-v` run; count must equal `collected`).
- G08 covers utcnow / naive `datetime.now()` across `core/`, `engine/`, `markets/`,
  `cli/`, `config_loader.py`; the `@dataclass` ban stays `core/`-only.
- All mypy invocations use a temp `--cache-dir` outside the repo (removed by the gate);
  ruff runs `--no-cache`; all children run with `PYTHONDONTWRITEBYTECODE=1`.

## Corrections to earlier claims (this session)

- **The old G10 literal guard was vacuous on Windows** until commit `f58c760`: the
  scanner emits os-native paths (`src\niveshdristi\...`) while the test filter compared
  forward-slash prefixes, so `test_core_no_market_literals` and
  `test_engine_no_market_literals` matched nothing and could not fail. A real violation
  (`core/instrument.py:17` docstring naming "NSE") was live and invisible; fixed in
  `ebe8aa7` and the guard made non-vacuous in `f58c760` (normalization + non-vacuity
  assertions + a Windows-path regression test). Gate G10 now scans both `core/` and
  `engine/` from the repo root.
- **`nd --json validate` produced invalid JSON** on narrow terminals: Rich wrapped the
  JSON at terminal width and inserted newlines inside string literals (failed
  `json.loads` at COLUMNS=40, passed at 200). Root cause and fix in `85198c1`:
  `_output()` prints plain width-independent JSON; diagnostics go to stderr.
- **Config MD5 (gate G04, both trees match)**: `00fb409ae0b8bcd2e21548847d186fe0`.
  The previously documented `0f2ad5235d7082aaad4a26bf5f1554c3` is stale.
- `arbitrary_types_allowed` does **not** appear anywhere in the package (removed in
  `02c3b1a`); the gate's justification-comment check (G09) is currently vacuously true.

## Legacy-equality caveat (read before trusting G04/G05)

G04/G05 prove the legacy config values and backtest outputs are byte-identical between
the Phase 0 worktree (`82f76d8`) and HEAD. They therefore **certify KNOWN-BUGGY legacy
behavior** until Phase 5 replaces it: flat `cost_bps=15` instead of the cost model, a
dead `_compute_cost_bps`, `backtest.costs`/`backtest.timing` attribute-access crashes,
look-ahead fundamentals (`as_of = date.today()`), and a survivorship-biased static 2024
Nifty universe (see `docs/AUDIT.md` §3–4 and `docs/PHASE2_PREREQS.md`). A green G04/G05
is a regression guard, not an endorsement.

## phase0_wt is not a pristine checkout

`D:\Nivesh Dristi\phase0_wt` is at commit `82f76d8` but holds two **untracked** tool
copies (`tools/dump_config.py`, `tools/compare_backtest.py` — both post-82f76d8 files,
md5-identical to the repo copies). Gate G03b verifies the md5 match before every
G04/G05 comparison. Do not modify the worktree during gate runs.

## What Phase 1 delivered (commits on rebuild/v2)

- Typed CFG restored in `config.py`; layered loader in `config_loader.py`
  (env > user config > defaults), unknown-key validation for mandate/universe/strategy
  YAML (`82af57b`, `49bddd7`, `4b01a47`).
- `core/`: 7 Pydantic v2 frozen model modules; `markets/` registry + `in_nse/` profile
  with holidays/costs/tax/sectors/asm_gsm/fno_ban YAML; `cli/` Typer `nd` with real
  `validate` (8 checks, unknown-key rejection, exit codes); `engine/advance()` stub
  (`9cf9c85`, `e099b95`, `d1e8328`).
- Universes carry `as_of`/`source`/`approximate` metadata (`0a5044e`).
- Literal guard repaired and non-vacuous; CLI JSON pure; gate with single-run,
  zero-write design and phase0 precheck (`ebe8aa7`, `f58c760`, `85198c1`, `5e5f43b`,
  `cb620f4`, `cdbba61`).
- `docs/CLAUDE_CODE_PROMPT.md` added (working rules now live in the repo).

## Phase 2 prerequisites and risks

Kept as listed in `docs/PHASE2_PREREQS.md` (not reproduced or invented here):
2026 holidays missing (the strict xfail); universe ticker counts need as-of
constituents (nifty50=49, nifty100=101); `pg_dsn` returns the literal
'${DATABASE_URL}' (root `config.yaml:8`) — this was true at Phase 1 close;
exact `${VAR}` expansion was implemented in Phase 2 S1 (commit `3882feb`);
legacy backtest latent bugs; unverified rates (all items in `docs/VERIFY.md` are
unverified); legacy mypy/ruff baselines. Environment risk: the suite is only proven on
Python 3.13.7/Windows; 3.11 could not be checked because no 3.11 interpreter exists
here.

---

# Phase 2 Progress (P0 probe + steps S1–S8, 2026-10-24)

## P0 live data-source probe (read-only; raw outputs in D:/Nivesh Dristi/p2_probe/)

Verdicts (details in docs/VERIFY.md §9): yfinance **usable** (unofficial,
prices fallback; 2015→today verified live); NSE bhavcopy via archives
**usable with caveats** (single-file probe returned 3,542 rows with
DELIV_QTY/DELIV_PER; 2015 paths 404); jugaad-data 0.37 **bhavcopy-only**
(index/TRI functions broken: internal TypeError); niftyindices.com,
nseindia.com main site (holidays/filings/constituents), NSDL FII/DII
**blocked** (timeout / Akamai 403 / connection reset). No block was worked
around; no automated NSE/NSDL/niftyindices requests beyond the one-off
probes above.

**NSE ToS gray zone (2026-10):** nseindia.com Terms of Use prohibit
"systematic or automated data collection"; robots.txt allows "/" (only
/market-data-test disallowed). Project decision: bhavcopy is FILE-BASED —
the user downloads files manually in a browser; there is no automated
downloader.

## The three blocked Phase 2 items and what unblocks each

1. **Official 2026 holidays** — NSE site unreachable automatically. Unblocked
   by: the user downloading the official NSE holiday page/PDF in a browser
   and providing it; then the pre-agreed single commit (data + xfail-marker
   removal + gate G06/G15 update, with explicit approval). The strict xfail stays
   untouched until then.
2. **As-of index constituents (nifty50=49, nifty100=101)** — no responding
   free source; historical as-of constituents (incl. delisted) need a
   licensed feed or manual archives. Currently blocked.
3. **Announcement-dated fundamentals** — no responding source provides
   announced_at (yfinance is current-state). PIT schema + frozen
   invisibility test exist (S8); real announcement dates blocked.

Also still open: **Python 3.11 is not installed** on this machine
(`py --list` shows only 3.13), so the 3.11 verification run could not
happen; suite is proven on global Python 3.13.7 / pytest 9.1.1 only.

## Steps S1–S8 (one commit each; gate GATE: PASS after every commit)

- **S1** `3882feb` — `${VAR}` expansion (exact whole-string form) in
  config_loader; unset vars keep the literal with a warning naming only the
  variable. Proven with gate runs under default env and
  `DATABASE_URL=<dummy>` (G04 PASS both; pg_dsn took
  the dummy value when set). A fully-unset gate run is impossible while
  .env defines DATABASE_URL — covered by unit test instead.
  **The config MD5 is environment-dependent**: `00fb409a…` under the default
  env, `af22c29c…` with DATABASE_URL set to a dummy. G04 compares the two
  trees WITHIN the same run — the absolute MD5 value is not a constant.
- **S2** `36dd886` — `src/niveshdristi/marketdata/` (name chosen because
  `niveshdristi.data` is the LEGACY package): DataClient protocol +
  PriceSeries (raw/adjusted separate, flags) + ProviderRegistry. Gate now
  covers marketdata/ in G08 hygiene, G10 literal scan (neutral zone), G13
  ruff, G14 mypy; market literals allowed only in an explicit adapter
  allowlist under markets/in_nse/providers/. Each extension proven
  fail-able with seeded one-off files.
- **S3** `c190714` — YFinanceClient (IN_NSE): `.NS` suffix only inside the
  adapter, lazy yfinance import, raw + adjusted fetched separately,
  NaN-OHLC rows FLAGGED not dropped (reproduced live on 2026-10-23),
  unsupported kinds raise NotImplementedError. `tools/probe_yfinance.py`
  live smoke (opt-in, never run by pytest/gate). pyproject gained the one
  allowed extra edit: `data = ["yfinance>=1.5"]`.
- **S4** `ed8a9f9` — bhavcopy FILE parser: exact official schema (fails
  loudly on mismatch), typed DELIV_QTY/DELIV_PER, date-keyed, "-" → null,
  strip of real-file padding spaces. Tests use a SYNTHETIC fixture labeled
  inside the file; `tools/bhavcopy_check.py` is the opt-in real-file
  checker (verified against the P0 file: 3,542 rows parsed, EQ mean
  DELIV_PER 55.49). No real NSE data committed.
- **S5** `23e097c` — Parquet cache (market-neutral): deterministic sha256
  keys, second identical call is a cache hit, live queries honour
  max_age, as_of-pinned queries are immutable (never stale). Tests write
  only under tmp_path.
- **S6** `1f9e023` — ordered provider chain: retries, fallback on error or
  unsupported, ALL-fail raises typed ProviderError (never an empty frame);
  chain order is registry-driven (default IN_NSE prices: yfinance;
  bhavcopy enriches with delivery data — not primary).
- **S7** `cd76aed` — data-quality report object: nan_ohl, zero_volume,
  weekday gaps, stale_bars, split_discontinuity (critical) — planted
  defects fixture proves all fire; clean data yields zero issues.
- **S8** `c72c64b` — PIT store: period_end/announced_at/source, as_of
  queries, conservative-lag `put_with_lag` (approximate=True, off by
  default). FROZEN TEST: a result announced tomorrow is invisible today.

## Current verified state

Fresh full gate run, 2026-10-24 (after closeout commit `9e68591`):

```
PASS G01 git status clean before pytest
INFO PYTEST pytest runs: 1
INFO PYTEST ================= 147 passed, 1 xfailed, 2 warnings in 6.47s ==================
PASS G01 git status clean after pytest
PASS G02 No stray test/check/bak files
PASS G03 Legacy contract intact / PASS G03 No additions to legacy folders
PASS G03b tools/dump_config.py md5 match: 7446cc0050965dd2aa05e2c506a00026
PASS G03b tools/compare_backtest.py md5 match: 2f75d57b1d55e0e932d71a5122c58365
PASS G04 Config MD5 match: 00fb409ae0b8bcd2e21548847d186fe0 (+ both __file__ PASS)
PASS G05 Backtest outputs match (+ both __file__ PASS)
PASS G06 collected=148 passed=147 failed=0 errors=0 xfailed=1 skipped=0
PASS G06 all 148 collected node IDs under tests/
PASS G07 No utcnow warnings
PASS G08 Time & dataclass hygiene clean (21 files)
PASS G09 All arbitrary_types_allowed have justification
PASS G10 Neutral zones (core/engine/marketdata) have 0 findings
PASS G10 Adapter allowlist enforced (bhavcopy_file.py, yfinance_adapter.py)
PASS G10 core: 7 files / engine: 2 files / marketdata: 7 files covered
PASS G10 Temp tree reports all 5 patterns
PASS G11 Typed CFG works (attr-defined error for does_not_exist)
PASS G12 --json validate exits 0 with summary.failed == 0
PASS G12 --config <bad> --json validate exits 1
PASS G13 Ruff clean on new code paths
PASS G14 Mypy clean, type:ignore count=1
PASS G15 Exactly one xfail marker, strict=True
PASS G16 Docs exist, .gitignore contains .venv
PASS G18 (3 byte-identical legacy fixture rewrites; no changed/new/deleted files)
GATE: PASS
```

Figures: **148 collected, 147 passed, 0 failed, 0 errors, 0 skipped,
1 xfailed** (the approved strict holiday xfail), 2 known universe-count
warnings.

---

# Phase 3 (partial, 2026-10-24): seam, registry, TA port, gate G1

Gate hardening (G1): the model zones (alpha/, markets/in_nse/models/) ban
`date.today()` in addition to the existing time hygiene — **wrapped legacy
code is exempt** (it is not scanned; where a model wraps non-PIT-safe legacy
behaviour, its registry entry says "legacy, not PIT-safe"). G13/G14 now also
cover tests/test_alpha.py by explicit path.

**No-look-ahead caveat (plain statement):** the property test in
tests/test_alpha.py catches SIDE-CHANNEL peeking only (a model consulting an
as-of-unaware raw source). The REAL point-in-time guard is the builder's
construction-time DataError on any row dated after as_of
(marketdata.context.build_model_inputs).

TA ensemble: the legacy composite is a weighted sum of scorers clipped to
[-1, 1] and CAN be negative, so a NEW clamp into [0, 1] precedes the
conviction mapping (documented in the module docstring); a bounds test on
synthetic extremes enforces conviction ∈ [-1, 1]. The CFG-pinning assertions
in the equality test are an intentional tripwire against config drift.


## G2 (2026-10-24): builder aux validation, tests/ lint coverage, registry listing

- The ModelInputs builder now validates AUX frames by ROLE (DataError naming
  role and dates on future rows) and the truncating handle truncates them;
  the regime model's self-truncation is documented as a redundant second layer.
- Gate G13/G14 now lint/type-check every NEW test file; the explicit legacy
  exclusion list is in tools/phase1_gate.py (characterization, imports,
  create_fixtures, and the PROTECTED scanner tests/market_literals.py).
- CONVICTION SCALES ARE NOT COMPARABLE OR CALIBRATED across models, and no
  downstream combiner may treat them as probabilities until Phase 4
  validation exists (stated in alpha/registry.py and here).
- Registry listing (command output, G2c): ta_ensemble(10), price_range(5),
  momentum_ts(20), momentum_cs(20), mean_reversion(10), low_volatility(60),
  regime(5) — all pit_safe=True, data_status=live.

---

# Phase 3 (complete, 2026-10-24): all spec models registered and tested

## Model registry (raw `nd --json models` output; composition point = the CLI command)

```
count: 16
block_deals              horizon= 20 data=filings                  pit=True status=stub
delivery_anomaly         horizon= 10 data=prices                   pit=True status=live
earnings_drift           horizon= 20 data=fundamentals,prices      pit=True status=stub
fii_dii_regime           horizon= 20 data=flows                    pit=True status=stub
fundamental_guardrails   horizon= 60 data=fundamentals             pit=True status=stub
low_volatility           horizon= 60 data=prices                   pit=True status=live
macro_overlay            horizon= 20 data=prices                   pit=True status=stub
mean_reversion           horizon= 10 data=prices                   pit=True status=live
momentum_cs              horizon= 20 data=prices                   pit=True status=live
momentum_ts              horizon= 20 data=prices                   pit=True status=live
price_range              horizon=  5 data=prices                   pit=True status=live
promoter_pledge          horizon= 60 data=filings                  pit=True status=stub
quality_value            horizon= 60 data=fundamentals             pit=True status=stub
regime                   horizon=  5 data=prices                   pit=True status=live
sector_rotation          horizon= 20 data=prices                   pit=True status=stub
ta_ensemble              horizon= 10 data=prices                   pit=True status=live
```

live vs stub, and WHY: **live** = computed purely from supplied price/aux
frames (ta_ensemble, price_range, momentum×2, mean_reversion,
low_volatility, regime, delivery_anomaly). **stub** = maths exists but no
verified data source: fundamentals/announced_at (fundamental_guardrails,
quality_value, earnings_drift), sector indices (sector_rotation), flows
(fii_dii_regime), filings/deals (promoter_pledge, block_deals), macro
factors (macro_overlay).

PORTS vs NEW: **ported (import-only, equality-tested)**: ta_ensemble
(indicators + signal engine), fundamental_guardrails (check_guardrails rules
maths only), sector_rotation (compute_rrg + market_regime; NOTE: no legacy
golden exists for compute_rrg — the equality test compares wrapper vs direct
legacy call, no golden file pretends legacy correctness). **NEW**:
price_range (no legacy implementation existed), all quant models, all India
models, every conviction mapping, quality score, macro overlay.

## Spec conformance (S12)

tests/test_alpha.py::TestPhase3SpecConformance enumerates the Phase 3 model
list (HMM optional, not required) and fails the build if any is missing from
the registry, lacks a horizon, or has no unit-test reference. Proven
fail-able with a seeded missing id (raw output in the session log).

## R1 dependency finding (2026-10-24)

legacy fundamentals/loader.py (imported read-only by the guardrails port for
check_guardrails) imports yfinance AND asyncpg at top level. Both are MAIN
dependencies in pyproject [project.dependencies] (yfinance>=0.2.40,
asyncpg>=0.29; the optional 'data' extra adds yfinance>=1.5), so the suite
does NOT fail on import in any environment installed from main deps. The
new-code layer's yfinance-free goal therefore holds only transitively; if
main deps ever drop yfinance/asyncpg, the guardrails port would need the
rules maths inlined (requires explicit approval — it would be a copy, not a
port).

## Standing caveats

- CONVICTION SCALES ARE NOT COMPARABLE OR CALIBRATED across models; no
  downstream combiner may treat them as probabilities until Phase 4.
- The no-look-ahead property test catches side-channel peeking only; the
  real PIT guard is the builder's DataError on future rows.
- Blocked data items (holidays/constituents/announced_at) remain blocked.

---

# Phase 4 (complete, 2026-10-25): portfolio, risk, execution, costs

## Tasks and commits (one per task, GATE: PASS after each)

- S0 `2c88c8a` loop-aware _run_async (sector rotation works inside event loops)
- S1a `182b996` core MarketRules neutral view + profile converter
- S1 `052b9ea` portfolio/construction (conviction -> weights, long-only clamp)
- S2 `63ce1c4` risk-gate chain (logged clamps, inert-gate skips, final validation)
- S3 `147bd25` strict costs/tax YAML loaders; profile now LOADS the YAMLs; execution/costs engine
- S4 `42e9030` calendar-month capital-gains tax engine with FY-aware set-off
- S5 `32a624c` gated order builder, Broker protocol, SimBroker (circuit limits, liquidity slippage)
- S6 `f2f2000` PaperBroker (local persistence) + the two spec tests (gross vs net)
- S7 `c000b16` strategy blending as fixed linear weights over model signals

## FINDING: the YAMLs were never loaded

Until P4-S3 the rates in markets/in_nse/costs.yaml and tax.yaml had NO
loader — markets/in_nse/profile.py hardcoded identical values (R2 audit:
all equal). Now profile.py builds CostModel/TaxModel FROM the YAMLs via the
strict loaders (unknown keys rejected; percent-style values in fraction
fields rejected loudly; verified=true requires source+date). SINGLE-SOURCE
RULE: new code reads only the profile YAMLs; legacy config.yaml is frozen,
untouched, and carries the SAME key names in PERCENT units (see units
table) — never read by new code.

## Rate table (from costs.yaml / tax.yaml; EVERY value # VERIFY)

brokerage_per_order 20.0 (currency) | stt_delivery_buy 0.001 | stt_delivery_sell
0.001 | stt_intraday_sell 0.00025 (IGNORED: v1 delivery-only) |
exchange_charges 0.0000345 (DOUBTFUL per VERIFY 4) | sebi 0.000001 | stamp
0.00015 | gst 0.18 | slippage 5.0 bps | dp 13.5 (currency) | tax: threshold
365d/12m | STCG 0.20 | LTCG 0.125 | exemption 125,000 | setoff 8y. The 2024
tax rates may have changed in later budgets; all remain unverified.

## Units table (misreading guard: *_pct keys hold FRACTIONS in the YAMLs)

| key | YAML unit | human | legacy config.yaml (PERCENT units) |
|---|---|---|---|
| stt_delivery_sell_pct | fraction 0.001 | 0.1% | 0.1 |
| stt_intraday_sell_pct | fraction 0.00025 | 0.025% | 0.025 |
| exchange_charges_pct | fraction 0.0000345 | 0.00345% | 0.00345 |
| sebi_fees_pct | fraction 0.000001 | 0.0001% | 0.0001 |
| stamp_duty_buy_pct | fraction 0.00015 | 0.015% | 0.015 |
| gst_pct | fraction 0.18 | 18% | 18.0 |
| brokerage_per_order / dp | currency | — | 20.0 / absent |
| slippage_bps | bps | 5 bps | 5.0 |

## RATES UNVERIFIED propagation contract

Every CostBreakdown/TaxResult carries rates_used (fraction AND human form),
rates_verified (currently always False), and the banner "RATES UNVERIFIED"
when unverified. Net-of-cost reports cannot hide the flag (tested).

## Documented UNVERIFIED assumptions

Delivery-only (intraday levy field deliberately ignored); levy on both buy
and sell; stamp duty buy-only; depository per-scrip charge once per SELL
order; GST base = brokerage + exchange + regulator fees (depository charge
EXCLUDED); slippage reported separately from fees; circuit bands simulated
from profile-level config (per-symbol band data has NO source — fixture
only); settlement T+1 recorded as a NUMBER only (date arithmetic waits for
the Phase 5 calendar); floats acceptable for v1 simulation (Phase 6 ledger
must use integer minor units or Decimal).

## Legacy coexistence

The legacy backtest (flat cost_bps=15, dead _compute_cost_bps) is frozen
and G04/G05 keep certifying it unchanged. New engines live in portfolio/
and execution/ beside it; nothing in Phase 4 edited any legacy file.

## What Phase 5 still needs

Official 2026 holidays (still blocked); VERIFIED rates (VERIFY 1-5 all
open); a symbol->sector map source; market-cap data source; per-symbol
circuit-band data; as-of constituents; announcement-dated fundamentals.

**R4a convention finding (2026-10-25, pre-Phase-5):** SPEC TEST 2's "costs"
counts FEES only; slippage is embedded in fill prices and NOT added back,
so its "gross" (990,261.70) is before fees but AFTER slippage — it
understates the true all-in drag (~534 bps of NAV, not 437). No double
count. Phase 5 must adopt ONE convention: gross = before ALL frictions.
