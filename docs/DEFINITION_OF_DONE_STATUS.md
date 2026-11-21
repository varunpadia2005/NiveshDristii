# Definition-of-done status (NEW, P10-S7)

Against docs/CHANGES.md section 12 ("Definition of done (v1, India)"):

| # | Item | Status | Proof / blocker |
|---|---|---|---|
| 1 | `nd backtest` offline from cache, net-of-cost vs Nifty TRI + gate verdict | **PARTIAL** | `nd backtest run` (P10-S3) runs offline over stored snapshots with the gate verdict; **BLOCKED: no Nifty TRI source exists** (docs/VERIFY.md §13) — benchmark comparison is unavailable by design. tests/test_cli.py::TestBacktestRunP10 |
| 2 | `nd paper create/tick/status/halt/resume` idempotent, ledger verifies | **DONE-TESTED** | test_tick_idempotent_noop_byte_for_byte; TestPaperLedger (verify/tamper); test_paper_cli.py |
| 3 | Every legacy analytic an AlphaModel; ≥5 new, 3 India-specific | **DONE-TESTED** | alpha/quant/* registry tests (test_alpha.py); 3 India-specific: ta_ensemble, regime, sector_rotation (stubs honestly labelled) |
| 4 | LLM narrator grounded, schema-valid; lying-LLM rejected | **DONE-TESTED** | tests/test_llm.py (validate_output rejection tests), test_llm_safety.py (24-payload injection set) — narrator personas themselves are DEFERRED (P7 scope excluded by binding R2) |
| 5 | Streamlit six pages, as-of stamps + disclaimers | **DONE-TESTED** | tests/test_ui.py (all pages render banners + data-derived as-of); manual checklist docs/UI_MANUAL_CHECKLIST.md |
| 6 | US profile smoke test, zero core/engine edits | **DONE-TESTED** | tests/test_two_market.py (core/engine diff vs 6948457 asserted EMPTY inside the test; costs_not_modeled now first-class per D4) |
| 7 | CI green, no network calls in tests | **PARTIAL** | .github/workflows/ci.yml written (docs/CI.md) — NOT RUN (needs your 3 action SHAs, then push); offline-ness proven structurally (shell providers, FakeLLM, G18) |

Plain statement: items 1 and 7 are partial for the same two reasons the
whole project carries — no verified TRI source, and CI not yet pushed.
Everything else is done and tested.

## P11-A updates (2026-11-13)

- Item 7 (CI green): the branch IS pushed (rebuild/v2 at 96408f3+,
  tag p9-complete) but the workflow's action pins remain
  placeholders ({SHA:*} unfilled, INPUT-2 not supplied) — CI has STILL
  never run; a real Actions run remains NOT RUN. The live-fetch window
  defect found by the audit is fixed (96408f3).
- Phase 11-A closed: docs consistency guards, TrialRecorder wiring at
  the services caller (item 1's gate-verdict data accumulates via
  trials_recorded), FX-J closed as DROPPED (user decision).
- Still open: TRI source (item 1), CI run (item 7), US-usable
  milestone, 4 stub models, verified IN rates, api/app frozen
  (accepted out of scope), the type: ignore at engine/advance.py:425,
  Python 3.11 never run locally.

## P14-B update (2026-11-21)

docs/US_DATA_CHECKLIST.md added: every external US-market input (12
cost fields, 6 tax fields, holidays, benchmark, FX, provider, 4 stub
models) with destination file, field names, the validation it must
pass, before/after behavior, "SOURCE REQUIRED" slots and the ordered
"US usable" milestone sequence. No data — slots only.

## P13-B update (2026-11-22)

The 2 ubuntu-only CI test failures (run 44864471561) were FIXED and
CI run 44870432495 is FULLY GREEN again — all three jobs success
(gate ubuntu, gate windows, coverage), now on the d7edbe2 tree with
the robust ANSI/wrap/prog-name guards. CI status: green, verified
from the API.

## P12-A update (2026-11-20)

`nd data fetch`, `nd data refresh` and `nd signals generate` are
IMPLEMENTED (previously interface-stability stubs): fetch/refresh go
through the market DataClient seams (IN_NSE yfinance adapter; US_NYSE
typed shell refusal), signals through the same seam + the live model
bundle + blend. Report-only JSON; nothing stored; replay untouched.
CI run 44777085656: all three jobs success (third consecutive green
run, now with 681 tests).

## P11-A13 update (2026-11-19)

Item 7 stays ACHIEVED — the second consecutive fully green CI run
(44576161117) now runs on the raised floor: requires-python ">=3.13"
(3.11 removed; the claimed-but-untested 3.11 risk is CLOSED by
removing the claim). The tool configs (ruff py313, mypy 3.13) produce
byte-identical results. Two consecutive fully green CI runs quoted in
PROGRESS Phase 11-A12/A13.

## P11-A12 update (2026-11-19)

Item 7 (CI green): **ACHIEVED** — CI run 44567084480 (head 6c60c30)
completed with ALL THREE jobs success (gate ubuntu 3.13, gate windows
3.13, coverage). The chain of fixes: pins resolved (A4), 3.11 cells
dropped (A7), worktree outside the tree (A9), the two-market guard
base repaired (A7), the fixture-JSON fallback (A8), the warm-up step
(A10), and PYTHONPYCACHEPREFIX at the gate step (A12). Item 7's proof
is the API's raw per-job conclusions, quoted in PROGRESS Phase 11-A12.

## P11-A8 update (2026-11-16)

The three A7-approved fixes are applied and VERIFIED in a production-
form offline simulation: G04/G05/G06 (the checks that failed in CI)
now ALL PASS with the relative --phase0, scoped collection, and the
worktree mkdir; the fixture-JSON dirt is gone (fallback). ONE blocker
remains before a green CI run: the phase0 worktree lives INSIDE the
repo tree (untracked-dir noise in G01 + G18 parquet flags). Fix
proposed (needs approval): move the worktree outside the tree
($RUNNER_TEMP) in ci.yml. CI run status: NOT VERIFIED (push deferred
pending that approval).

## Phase 16-C update (2026-11-21)

CI fully green again: run 44928932419 (head c0a9ac7) — gate ubuntu,
gate windows, coverage ALL success, 696 passed + 1 strict xfail. The
windows-only gate failure was the module-help test's subprocess
decoding (cp1252 pipe); fixed test-side under explicit authorization.

## P11-A7 update (2026-11-14)

CI run 43620550944 (head bc34ab3): coverage job **SUCCESS** (first
green job in the project's CI history); the two matrix gate jobs fail
only on the three pre-diagnosed findings (RC-4 pytest collection of
the worktree's frozen tests, RC-5 fixture-JSON CRLF dirtying, RC-6
relative --phase0 PYTHONPATH) — each documented in PROGRESS with a
proposed fix awaiting user approval. Pins, install, bootstrap,
worktree: all verified working in production.

## P11-A5 update (2026-11-14)

The P11-A4 "NEEDS-APPROVAL" yfinance finding is **RETRACTED**: a real
fresh-venv run with exactly CI's install (`.[dev]`) collects all 659
tests cleanly — yfinance is a MAIN dependency and CI installs it
regardless. The approved `.[dev,data]` change was NOT applied (nothing
to fix). The CI install gap is CLOSED (there never was one); the only
remaining gate to a green first CI run is the real Actions run itself
(NOT RUN until the user pushes). Fresh-venv suite: 657 passed, 1
xfailed, 1 failed — the failure is the git-history test inside a
.git-less archive export (environment artifact).

## P11-A4 update (2026-11-14)

Item 7 (CI green) — the pin placeholders are CLOSED: all five `uses:`
lines in ci.yml are pinned to 40-hex SHAs resolved from the official
action repos (checkout v5.1.0, setup-python v5.6.0, cache v4.3.0),
guarded by tests/test_ci_workflow_pins.py. A real Actions run remains
NOT RUN until the user pushes. NEW BLOCKER for a green first run:
the CI install ([dev] only) fails at collection on yfinance (finding
documented in PROGRESS Phase 11-A4 S3); the proposed fix
(".[dev,data]") needs the user's approval before it can be applied.

## P11-A2 update (2026-11-14)

S1 (NSE 2026 holidays) and S2 (CI action pins) remain BLOCKED: the
supplied inputs were blank again; never filled by the agent. The live
yfinance probe remains NOT RUN (INPUT-3 unanswered). The S5 fake
signature accommodation is now disclosed in PROGRESS.md with a
consistency guard (f346a57).

## P10-S7 updates

Item 7 (CI green): CI workflow exists but has NOT run (needs the 3 action
SHAs and a push). Status stays PARTIAL.
Item 1 (offline backtest vs Nifty TRI): still PARTIAL — no TRI source.
