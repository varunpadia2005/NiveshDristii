"""P11-A7-S2: the CI matrix may only claim Python versions the constraints
freeze actually supports.

constraints/ci-constraints.txt is a working-venv freeze recorded at the
Phase 10 baseline on Windows x Python 3.13.7 (docs/CI.md, provenance
section) — scipy 1.18.1 in that freeze has NO 3.11 distribution, proven
by CI run 43574549786 (both 3.11 cells: ResolutionImpossible at
install). The matrix therefore may only list versions derivable from a
tracked provenance source: docs/CI.md's freeze line (3.13).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _allowed_versions() -> list[str]:
    """Derive the allowed matrix versions from the tracked freeze
    provenance in docs/CI.md (the recorded freeze interpreter)."""
    ci_md = (REPO / "docs" / "CI.md").read_text(encoding="utf-8")
    m = re.search(r"Windows ×\s*3\.(\d+)\.(\d+)", ci_md)
    assert m, (
        "the freeze provenance line disappeared from docs/CI.md — "
        "this guard cannot derive the allowed versions; update it "
        "deliberately"
    )
    return [f"3.{m.group(1)}"]


class TestCiMatrixVersions:
    def test_matrix_versions_match_the_constraints_freeze(self):
        wf = (REPO / ".github" / "workflows" / "ci.yml")
        data = yaml.safe_load(wf.read_text(encoding="utf-8"))
        matrix = data["jobs"]["gate"]["strategy"]["matrix"]
        versions = matrix["python-version"]
        assert isinstance(versions, list), (
            "non-vacuity: matrix python-version is not a list"
        )
        assert len(versions) >= 1, (
            "non-vacuity: the matrix lists no python versions"
        )
        allowed = _allowed_versions()
        bad = [v for v in versions if str(v) not in allowed]
        assert not bad, (
            f"matrix python-version {bad} is NOT covered by the "
            f"constraints freeze (allowed: {allowed}); the install step "
            "cannot resolve on uncovered versions (CI run 43574549786)"
        )
