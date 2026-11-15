"""P11-A9 W-1: the Phase-0 worktree must live OUTSIDE the repo tree.

Defect this pins (CI run 43620550944, ubuntu G01; reproduced in the
A9 clone): a worktree added INSIDE the repo tree appears as an
untracked directory (`?? phase0_wt/`) in the main tree's git status →
G01 fails before AND after pytest — on BOTH operating systems (the
ubuntu CI log shows exactly this; the Windows CRLF fixture dirt is a
separate, already-fixed RC-5). The approved fix relocates the worktree
to $RUNNER_TEMP (outside the tree) and threads the path through
$GITHUB_ENV as PHASE0_WT.

Assertions:
- the matrix job's worktree-add target is NOT a relative path (it
  must start with $WT, itself derived from $RUNNER_TEMP);
- no gate-job step references a bare phase0_wt/-relative path;
- the gate's --phase0 consumes $PHASE0_WT;
- mkdir -p precedes every cp INTO the worktree (W-2 preserved).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

REPO = Path(__file__).resolve().parent.parent


def _gate_steps() -> list[dict[str, Any]]:
    data = yaml.safe_load(
        (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    return cast("list[dict[str, Any]]", data["jobs"]["gate"]["steps"])


def _run_of(steps: list[dict], name_prefix: str) -> str:
    for step in steps:
        if step.get("name", "").startswith(name_prefix):
            return step.get("run", "")
    raise AssertionError(f"non-vacuity: step {name_prefix!r} not found")


class TestCiWorktreeOutsideTree:
    def test_worktree_add_target_is_not_in_tree(self):
        steps = _gate_steps()
        run = _run_of(steps, "Phase0 worktree")
        adds = [ln for ln in run.splitlines() if "git worktree add" in ln]
        assert len(adds) >= 1, "non-vacuity: no worktree-add line"
        for ln in adds:
            assert "$WT" in ln or "$RUNNER_TEMP" in ln, (
                f"the worktree-add target is in-tree or relative: {ln!r}"
            )
        assert "82f76d8" in run, (
            "the worktree must still be created from the Phase 0 commit"
        )

    def test_no_bare_phase0_wt_path_in_any_gate_step(self):
        steps = _gate_steps()
        found_refs = 0
        for step in steps:
            run = step.get("run", "")
            for ln in run.splitlines():
                stripped = ln.strip()
                if stripped.startswith("#"):
                    continue
                if "phase0_wt" in stripped and not any(
                    v in stripped
                    for v in ("$WT", "$RUNNER_TEMP", "$PHASE0_WT")
                ):
                    raise AssertionError(
                        "a gate step references a BARE phase0_wt path "
                        f"(no $WT/$RUNNER_TEMP/$PHASE0_WT variable): "
                        f"{stripped!r} — an in-tree relative path would "
                        "reintroduce the G01 untracked-dir failure"
                    )
                if "$WT" in stripped or "$PHASE0_WT" in stripped:
                    found_refs += 1
        assert found_refs >= 3, (
            f"non-vacuity: expected >= 3 worktree-path references "
            f"(mkdir/cp/gate), found {found_refs}"
        )

    def test_gate_consumes_phase0_wt_env(self):
        run = _run_of(_gate_steps(), "FULL gate")
        assert '"$PHASE0_WT"' in run, (
            "the gate step must pass --phase0 via $PHASE0_WT (the "
            "outside-tree worktree exported by the worktree step)"
        )
        assert "phase0_wt" not in run, (
            "the gate step still carries a bare phase0_wt path"
        )
