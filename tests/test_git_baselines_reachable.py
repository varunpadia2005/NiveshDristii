"""P11-A7-S1: every hard-coded git BASE commit in tests/ and tools/ must be
reachable from HEAD.

Defect this pins: the two-market core/engine guard diffed against
6948457 — an AMENDED-AWAY P10-S2 commit reachable from no branch, tag
or remote (it lived only in one machine's reflog), so the test passed
locally and failed in ANY clone (proven in CI run 43574549786 and by a
full-clone repro). The base is now 04c1501 (the on-branch P10-S2
commit; tree-identical for core/ and engine/ — verified empty diff).

The guard inventories every git-base SHA hard-coded in tests/ and
tools/phase1_gate.py (grep for a hex string appearing inside a
"git"-command argument list), and asserts `git merge-base --is-ancestor
<sha> HEAD`. If no .git repository is present the test FAILS loudly
(never skips) — a baseline check must not silently pass on an
unversioned tree.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (file relative to repo, the git-base SHA found on a git-command line)
EXPECTED_BASES: list[tuple[str, str]] = [
    ("tests/test_two_market.py", "04c1501"),
    ("tools/phase1_gate.py", "82f76d8"),
]

_HEX_IN_GIT_LINE = re.compile(r'"git".*?\b([0-9a-f]{7,40})\b')


def _inventory() -> list[tuple[str, str]]:
    """Every 7+ hex token on a line that starts a git command in tests/
    or tools/phase1_gate.py, excluding pure numeric literals."""
    found: list[tuple[str, str]] = []
    numeric = re.compile(r"^\d+$")
    targets = sorted(REPO.glob("tests/test_*.py")) + [
        REPO / "tools" / "phase1_gate.py"
    ]
    for path in targets:
        for i, line in enumerate(path.splitlines() if False else
                                 path.read_text(encoding="utf-8").splitlines(), 1):
            if '"git"' not in line and "'git'" not in line:
                continue
            for m in _HEX_IN_GIT_LINE.finditer(line):
                sha = m.group(1)
                if numeric.fullmatch(sha) or re.fullmatch(r"[0f]{7,}", sha):
                    continue
                found.append(
                    (f"{path.relative_to(REPO).as_posix()}:{i}", sha))
    return found


class TestGitBaselinesReachable:
    def test_every_git_base_sha_is_reachable_from_head(self):
        git_dir = REPO / ".git"
        assert git_dir.exists(), (
            "FAIL loudly: no .git repository — baseline reachability "
            "cannot be checked on an unversioned tree; this guard must "
            "never run against a bare export"
        )
        found = _inventory()
        assert len(found) >= 2, (
            f"non-vacuity: expected >= 2 git-base SHAs, inventory found "
            f"{len(found)}: {found}"
        )
        failures = []
        for where, sha in found:
            proc = subprocess.run(
                ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                capture_output=True, text=True, cwd=REPO, timeout=60)
            if proc.returncode != 0:
                failures.append(
                    f"{where}: base {sha} is NOT an ancestor of HEAD "
                    f"({proc.stderr.strip() or 'unreachable'}) — the "
                    "test or gate using it will fail in any clone"
                )
        assert not failures, (
            "unreachable git baselines:\n" + "\n".join(failures)
        )

    def test_expected_bases_are_still_in_the_inventory(self):
        """Pin the two known bases so the inventory cannot silently
        shrink (a removed base would dodge the reachability check)."""
        found = _inventory()
        for rel, sha in EXPECTED_BASES:
            assert any(loc.startswith(rel) and s == sha for loc, s in found), (
                f"expected git base {sha!r} at {rel} is missing from the "
                f"inventory (found: {found}) — if it genuinely moved, "
                "update EXPECTED_BASES deliberately"
            )
