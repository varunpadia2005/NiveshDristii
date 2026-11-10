# Paper Fund Scheduler (Windows Task Scheduler)

NEW (Phase 6). This document describes MANUAL setup only — no code in this
repository registers a scheduled task automatically.

## Prerequisites

- A created paper fund: `nd paper create <fund-id>`
- The package installed or the repo on `PYTHONPATH`
- Network available at run time (the tick fetches EOD bars through the
  provider chain; yfinance is UNOFFICIAL — see docs/VERIFY.md section 9)

## The command the scheduled task runs

```
"C:\Path\To\Python313\python.exe" -m niveshdristi.cli paper tick <fund-id> --base "D:\funds" --as-of <YYYY-MM-DD>
```

Notes (F4):
- The module entry point is `niveshdristi.cli` (a `__main__` shim added in F4);
  `python -m niveshdristi.cli.main` also works. Both require the working
  directory ("Start in" in Task Scheduler) to be the REPO ROOT: config.yaml
  and universes/ are loaded with CWD-RELATIVE paths at import time, so even
  `--help` fails from any other directory.
- `--as-of` is optional; when omitted the tick uses the system date
  (cli/main.py). Pass it explicitly for reproducible runs.
```

```

Replace the python path with your interpreter (find it with
`python -c "import sys; print(sys.executable)"`) and `--base` with your
funds directory. If the repo is not pip-installed, prefix with:

```
set PYTHONPATH=D:\Nivesh Dristi\NiveshDristii\src&&
```

(the trailing `&&` is not a typo — it separates the env assignment from
the command in Task Scheduler's cmd.exe context).

## Task Scheduler setup (manual, GUI)

1. Open **Task Scheduler** → **Create Task** (not Basic Task).
2. **General** tab: name it (e.g. `niveshdristi-paper-tick`); select
   "Run whether user is logged on or not" only if the interpreter path is
   machine-wide; otherwise "Run only when user is logged on".
3. **Triggers** → New:
   - Daily, at e.g. **18:00** local time (AFTER the 15:30 close and after
     EOD data is published — never at 15:30 sharp, per CHANGES.md C11).
   - Check **"Run task as soon as possible after a scheduled start is
     missed"** (covers a powered-off laptop; the tick's catch-up handles
     up to 10 missed sessions).
   - Check **"Start only if the network connection is available"**.
4. **Actions** → New:
   - Program/script: the python.exe full path.
   - Arguments: `-m niveshdristi.cli paper tick <fund-id> --base "D:\funds"`
   - Start in: the repo root (so `config.yaml`/`universes/` resolve).
5. **Settings**: enable "Stop the task if it runs longer than 1 hour".
6. **Conditions**: uncheck "Start the task only if the computer is on AC
   power" if running on a laptop you want ticks from.

## Reading the last run result

- Task Scheduler: History tab or Last Run Result (0 = success, including
  logged NO-OPS; non-zero = failure).
- The fund directory: `events.jsonl` (one JSON object per tick/no-op/
  failure/halt/resume/recover/unlock), `heartbeat.json` (updated on every
  tick including no-ops), `ledger.jsonl` (append-only, hash-chained).

## Idempotence and holidays

- Ticking twice for the same session is a NO-OP (byte-for-byte unchanged
  ledger; exit code 0).
- The 2026 holiday list is NOT yet in this repo (docs/VERIFY.md section 7).
  The tick therefore treats a date with no valid EOD bars as a
  NON-SESSION: a logged no-op, exit code 0. Holidays are never inferred or
  invented.

## Halting

- `nd paper halt <fund-id> --reason "investigating"` — writes the flag.
- A halted fund's tick is a logged no-op.
- `nd paper resume <fund-id> --note "fixed"` — clears the flag (note
  required, logged).
- `nd paper verify <fund-id>` — verify the ledger hash chain.
- `nd paper recover <fund-id>` — OPERATOR: rebuild the broker cache from
  the ledger (never called by the tick).
- `nd paper unlock <fund-id>` — OPERATOR: remove a stale tick lock
  (logged). Never automatic.

## Explicit scope statement

NO real broker integration, no order placement and no order endpoints
exist in Phase 6: execution is PaperBroker only. The paper fund can never
be labelled promotable — the DataLimitations banner on every report lists
the standing limitations (unverified rates, approximate universe,
derived calendar, adjusted-price basis, unavailable corporate actions).

## Alignment convention for the backtest-vs-paper equality test (R8)

The paper fund defers its first assessment: a fund created on date D
assesses from D+1. A backtest over the same frames assesses from the first
data session. For the records to correspond one-to-one, the test fund is
created the day BEFORE the first data session. Matching is by session_date
(no session is silently skipped: the test asserts
backtest_sessions == paper_sessions + (data sessions after the last ticked
one) + (data sessions on/before the created date)). The paper tick's
catch-up is capped at 10 sessions, so long histories are ticked once per
session in a loop.

## Verification (that the task exists and last ran)

```powershell
schtasks /query /tn "NiveshDristiTick" /v /fo LIST
```

Also check `<base>/<fund-id>/heartbeat.json` (mtime) and
`nd paper status` (last_session). Run the task once manually from the
Task Scheduler UI ("Run") before trusting the schedule.

## Snapshot retention trade-off

`nd paper prune-snapshots --keep-last 60 --apply` (P10-S6) deletes the
as-of snapshot parquet files of all but the last 60 sessions to bound
disk usage. TRADE-OFF: `nd paper replay` can only verify sessions whose
snapshots survive — pruned sessions are reported explicitly as
"snapshots unavailable" (never a silent pass). The LEDGER is never
pruned. If you need full-history replay, do not prune (or raise
--keep-last).


## Exit-code contract (FX-D)

`nd paper explain` is display-only: it exits 0 on ANY failure (missing
fund, no stored session, LLM error) and returns a no-op JSON payload
(R11: LLM-layer failures degrade to a logged no-op and never raise).
Every other fund-taking subcommand (status, verify, replay, tick, halt,
resume, recover, unlock, prune-snapshots) exits 1 on a missing fund with
a clean JSON error payload suggesting `nd paper create`.
