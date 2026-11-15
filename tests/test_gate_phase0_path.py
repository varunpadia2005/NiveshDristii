"""P11-A8-S1: the gate's --phase0 argument must be resolved to an ABSOLUTE
path before it is used as PYTHONPATH/cwd material.

Defect this pins (CI run 43620550944, both matrix jobs): ci.yml passes
the RELATIVE `--phase0 phase0_wt`; the gate then set
PYTHONPATH="phase0_wt/src" while cwd was ALREADY the phase0 worktree —
a dead entry — so the legacy comparator imported niveshdristi from the
editable install and G04/G05 failed ("Phase0 __file__ not under phase0
root"). The fix is `.resolve()` on the argument (RC-6, approved).

This guard PARSES the gate's code path (the module executes the whole
gate at import time, so importing is not an option); the assertion
targets the exact assignment line that feeds PYTHONPATH/cwd material.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "phase1_gate.py"


class TestGatePhase0Path:
    def test_phase0_arg_is_resolved_to_absolute(self):
        lines = GATE.read_text(encoding="utf-8").splitlines()
        candidates = [
            (i, ln)
            for i, ln in enumerate(lines, 1)
            if "--phase0" in ln and "Path(" in ln
        ]
        assert candidates, (
            "non-vacuity: the --phase0 assignment line is missing from "
            "tools/phase1_gate.py — if the argument handling moved, "
            "update this guard deliberately"
        )
        for i, ln in candidates:
            assert ".resolve()" in ln, (
                f"tools/phase1_gate.py:{i}: the --phase0 path is not "
                ".resolve()d; a RELATIVE --phase0 (as ci.yml passes it) "
                "makes the gate's PYTHONPATH/cwd material dead and "
                "breaks G04/G05 in any clone (RC-6)"
            )
