"""P11-A7-S3: the CI worktree step must create the target directory of
its own `cp`.

Defect this pins (CI run 43574549786, both 3.13 matrix jobs): the step
ran `git worktree add phase0_wt 82f76d8` then
`cp tools/… phase0_wt/tools/` — but the Phase 0 tree (82f76d8) has NO
tools/ directory, so the cp failed ("target 'phase0_wt/tools/': No
such file or directory"), the gate was skipped, and the
G04/G05-must-RUN step correctly failed the job. The fix is one
`mkdir -p phase0_wt/tools` before the cp.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _worktree_step_lines() -> list[str]:
    data = yaml.safe_load(
        (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    assert data["jobs"]["gate"]["strategy"]["matrix"]["python-version"], (
        "non-vacuity: the gate job matrix is empty"
    )
    steps = data["jobs"]["gate"]["steps"]
    for step in steps:
        run = step.get("run") or ""
        if "git worktree add phase0_wt" in run:
            return run.splitlines()
    raise AssertionError(
        "non-vacuity: no worktree step found in the gate job — "
        "if the step moved, update this guard deliberately"
    )


class TestCiWorktreeStep:
    def test_worktree_step_creates_the_cp_target_directory(self):
        lines = _worktree_step_lines()
        cp_i = next(
            i
            for i, ln in enumerate(lines)
            if ln.strip().startswith("cp tools/")
        )
        assert any(
            "mkdir -p phase0_wt/tools" in ln
            for ln in lines[:cp_i]
        ), (
            "the worktree step copies into phase0_wt/tools/ without "
            "creating it first; the Phase 0 tree (82f76d8) has no "
            "tools/ directory, so the cp fails in CI (run "
            "43574549786)"
        )
