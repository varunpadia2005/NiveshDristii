"""P16-A-4: guard the RC-5 fixture fallback in ci.yml (15-V F-m2).

The matrix job's fixture bootstrap rewrites tracked JSON fixtures with
native-CRLF bytes on Windows; the approved fallback restores the tracked
bytes with `git checkout -- tests/fixtures/`. In 15-V this line's
removal escaped the whole suite (no guard existed). This file pins:

- the gate job has a step named "Fixture bootstrap (F2 option A)";
- that step's run block contains the fallback line;
- the bootstrap step is ordered BEFORE the Phase0 worktree step and the
  FULL gate step (the fallback is useless after the gate starts);
- non-vacuity: all three step names are found.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

REPO = Path(__file__).resolve().parent.parent
FALLBACK = "git checkout -- tests/fixtures/"


def _gate_steps() -> list[dict[str, Any]]:
    data = yaml.safe_load(
        (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    return cast("list[dict[str, Any]]", data["jobs"]["gate"]["steps"])


def _step_index(steps: list[dict[str, Any]], name_prefix: str) -> int:
    for i, step in enumerate(steps):
        if step.get("name", "").startswith(name_prefix):
            return i
    raise AssertionError(f"non-vacuity: step {name_prefix!r} not found")


class TestCiFixtureFallbackGuard:
    def test_bootstrap_step_exists_and_carries_the_fallback(self):
        steps = _gate_steps()
        i = _step_index(steps, "Fixture bootstrap")
        run = cast(str, steps[i].get("run", ""))
        assert FALLBACK in run, (
            "the fixture-bootstrap step lost the RC-5 fallback "
            f"({FALLBACK!r}) — Windows CRLF fixture dirt would break G01 "
            "(15-V F-m2)"
        )

    def test_bootstrap_runs_before_worktree_and_gate(self):
        steps = _gate_steps()
        boot = _step_index(steps, "Fixture bootstrap")
        wt = _step_index(steps, "Phase0 worktree")
        gate = _step_index(steps, "FULL gate")
        assert boot < wt < gate, (
            f"step order drifted: bootstrap={boot}, worktree={wt}, "
            f"gate={gate} — the fallback must run before the gate"
        )
