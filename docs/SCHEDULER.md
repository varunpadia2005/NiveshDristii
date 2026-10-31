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
"C:\Path\To\Python313\python.exe" -m niveshdristi.cli paper tick <fund-id> --base "D:\funds"
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
