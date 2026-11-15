"""P11-A8-S3 (RC-4): the gate's pytest must collect ONLY tests/.

A bare `pytest -v` run from the repo root also collects the Phase-0
worktree's own frozen tests (phase0_wt/tests/*), which error at
collection and killed G06 in CI (run 43620550944) and in any clone
whose phase0_wt is complete. The gate's command now ends with the
`tests` path; G06's node-ID contract ("all collected node IDs under
tests/") stays unchanged and strict.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "phase1_gate.py"


class TestGatePytestScope:
    def test_gate_pytest_command_scopes_collection_to_tests(self):
        lines = GATE.read_text(encoding="utf-8").splitlines()
        cmd_lines = [
            (i, ln)
            for i, ln in enumerate(lines, 1)
            if '"-m", "pytest"' in ln
        ]
        assert cmd_lines, (
            "non-vacuity: the gate's pytest invocation is missing from "
            "tools/phase1_gate.py — if it moved, update this guard "
            "deliberately"
        )
        for i, ln in cmd_lines:
            assert re.search(r'"tests"\]', ln), (
                f"tools/phase1_gate.py:{i}: the gate's pytest command "
                "does not scope collection to tests/ — a phase0_wt/ "
                "worktree in the tree would break G06 with 2 collection "
                "errors (RC-4)"
            )
