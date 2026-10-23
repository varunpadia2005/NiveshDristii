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
