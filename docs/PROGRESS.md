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

## Test results (as they stand now)

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
  (`9cf9c85`, `91158c`, `e099b95`, `d1e8328`).
- Universes carry `as_of`/`source`/`approximate` metadata (`0a5044e`).
- Literal guard repaired and non-vacuous; CLI JSON pure; gate with single-run,
  zero-write design and phase0 precheck (`ebe8aa7`, `f58c760`, `85198c1`, `5e5f43b`,
  `cb620f4`, `cdbba61`).
- `docs/CLAUDE_CODE_PROMPT.md` added (working rules now live in the repo).

## Phase 2 prerequisites and risks

Kept as listed in `docs/PHASE2_PREREQS.md` (not reproduced or invented here):
2026 holidays missing (the strict xfail); universe ticker counts need as-of
constituents (nifty50=49, nifty100=101); `pg_dsn` returns the literal
'${DATABASE_URL}' (root `config.yaml:8`; no `${...}` expansion is implemented);
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
   and providing it; then the pre-agreed single commit (data + xfail removal
   + gate G06/G15 update, with explicit approval). The strict xfail stays
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
  `DATABASE_URL=postgresql://gate-dummy-2026` (G04 PASS both; pg_dsn took
  the dummy value when set). A fully-unset gate run is impossible while
  .env defines DATABASE_URL — covered by unit test instead.
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

```
$ python -m pytest -q            → 147 passed, 1 xfailed, 0 failed/skipped
$ python tools/phase1_gate.py --phase0 "D:\Nivesh Dristi\phase0_wt"
                                  → GATE: PASS (exit 0), pytest runs: 1
```
