"""P10-S4 (D6): the pip-audit wrapper refuses without --yes-network (offline
test ONLY — the tool itself is NEVER run with network by tests/gate/CI)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestPipAuditWrapper:
    def test_refuses_without_flag(self):
        proc = subprocess.run(
            [sys.executable, "tools/pip_audit.py"],
            capture_output=True, text=True, cwd=REPO, timeout=60,
        )
        assert proc.returncode == 2
        assert "EXACT COMMAND" in proc.stdout
        assert "Refusing" in proc.stderr
        assert "--yes-network" in proc.stderr

    def test_no_network_imports(self):
        src = (REPO / "tools" / "pip_audit.py").read_text(encoding="utf-8")
        for banned in ("requests", "urllib", "httpx", "socket"):
            assert banned not in src, banned
