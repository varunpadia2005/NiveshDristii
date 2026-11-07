# CI (NEW, P10-S1)

## What runs

`.github/workflows/ci.yml` — one job per matrix cell (Python 3.11 and 3.13
× ubuntu-latest and windows-latest), each executing the FULL phase gate:

```
python tools/phase1_gate.py --phase0 phase0_wt
```

which includes: clean-tree check, the complete offline pytest suite, the
literal guard (G10), ruff/mypy on new paths (G13/G14), the zero-write
proof (G18), and the LEGACY EQUALITY comparison against the frozen
phase0 snapshot 82f76d8 (G03b/G04/G05 — the config MD5 and the backtest
outputs must MATCH).

**G04/G05 must RUN**: a third step greps the gate log and fails the job if
either reports "Skipped" (D2).

## Setup the workflow does itself

1. checkout with fetch-depth 0 (the gate diffs against 82f76d8),
2. `python tests/create_fixtures.py` (the F2 option-A bootstrap),
3. `git worktree add phase0_wt 82f76d8` + copy the two frozen comparator
   tools + the fixture parquet (exactly docs/RESTORE.md's procedure),
4. `pip install -c constraints/ci-constraints.txt -e ".[dev]"` (D3).

## How to read a failure

The failing step prints the gate's named checks. Typical failures:
- `FAIL G06 collected=... failed=N` — a test broke; the pytest output in
  the log names the node.
- `FAIL G03 Legacy folders have changes` — someone edited a frozen file.
- `FAIL G18 ... zero-write` — a test wrote into the repo.
- `FAIL G14 Mypy errors` — type regression on new paths.
- `INFO G04 Skipped` treated as FAILURE by the dedicated step.
Matrix dimension in the job name tells you if it is OS- or version-specific.

## What YOU must fill in before the first run

Three action SHAs (policy: pin by commit SHA, tag noted in a comment):
- `{SHA:checkout}` → actions/checkout (v4/v5)
- `{SHA:setup-python}` → actions/setup-python (v5)
- `{SHA:cache}` → actions/cache (v4)

## Runtime estimate

~15–25 min wall clock for the 4-job matrix (suite ≈ 4.5 min + install
~2 min; Windows slower). pip cache keyed on pyproject + constraints.

## Reproducibility notes

- `constraints/ci-constraints.txt` records the working-venv resolution at
  the Phase 10 baseline (Windows × 3.13.7; 28 direct + 121 transitive).
  A different OS/Python may resolve different transitive versions — if
  that breaks a job, report it rather than editing by guess.
- Line endings: the workflow sets `autocrlf input` + hard-resets so the
  checkout is LF-consistent; `.gitattributes` (`* text=auto`) was
  D1-proven in a throwaway clone: legacy diff vs 82f76d8 stays EMPTY and
  G03b md5 comparison passes on both CRLF and LF trees (raw output in
  p10_evidence.txt).
- Nothing in the suite touches the network: providers are shells, LLM is
  FakeLLM, and the gate's G18 proves the repo is unmodified by the run.
