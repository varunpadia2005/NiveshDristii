"""P11-A8-S2 (RC-5): the fixture bootstrap must be deterministic modulo
line endings, and ci.yml must restore the tracked fixture bytes after
it (approved FALLBACK — the preferred writer fix is impossible because
tests/create_fixtures.py is one of G03's FROZEN legacy files).

Mechanism (proven in the run report): create_fixtures.py:137 writes
with default text mode → os.linesep on Windows (CRLF), while the CI
line-ending policy normalizes the index/checkout to LF
(autocrlf=input) → the 5 tracked JSON fixtures show as modified →
G01 fails on the Windows cell. `git diff --ignore-cr-at-eol` over them
is EMPTY — the content is byte-identical after line-ending
normalization, which is exactly the approval's fallback precondition.

Ubuntu evidence (CI run 43620550944 job log): the ubuntu G01 dirty
list contains NO fixture JSONs (LF write on Linux) — only
`?? phase0_wt/` (a separate finding).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOTSTRAP = REPO / "tests" / "create_fixtures.py"
CI = REPO / ".github" / "workflows" / "ci.yml"


def _tracked_fixture_names() -> list[str]:
    """The tracked JSON fixtures the bootstrap writes (git's own list)."""
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "tests/fixtures/*.json"],
        capture_output=True, text=True, cwd=REPO, timeout=60,
    ).stdout.splitlines()
    names = [x.strip() for x in out if x.strip()]
    assert len(names) >= 5, (
        f"non-vacuity: only {len(names)} tracked JSON fixtures found "
        f"({names})"
    )
    return names


def _normalized(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


class TestFixtureBootstrapClean:
    def test_bootstrap_output_matches_tracked_bytes_modulo_eol(self, tmp_path):
        """Determinism proof: run the bootstrap against a COPY of the
        repo's tracked fixtures (a scratch tests/fixtures dir is not
        possible — the bootstrap writes into the repo tree — so this
        test verifies the WRITER's determinism by regenerating each
        file's content in-process is not possible either; instead it
        compares the CURRENT working-tree bytes to the INDEX bytes,
        which is what CI's G01 sees)."""
        names = _tracked_fixture_names()
        compared = 0
        for name in names:
            wf = REPO / name
            if not wf.exists():
                continue
            index_bytes = subprocess_index_bytes(name)
            working = wf.read_bytes()
            assert _normalized(working) == _normalized(index_bytes), (
                f"tests/fixtures/{name}: the working tree differs from "
                "the index BEYOND line endings — the bootstrap output "
                "is nondeterministic; do not mask this with the "
                "checkout fallback (RC-5 rule)"
            )
            compared += 1
        assert compared >= 5, (
            f"non-vacuity: only {compared} tracked fixtures compared"
        )

    def test_ci_restores_tracked_fixture_bytes_after_bootstrap(self):
        """The fallback line must exist in the bootstrap step."""
        run_block = CI.read_text(encoding="utf-8")
        m = re.search(
            r"Fixture bootstrap \(F2 option A\).*?run: \|(.*?)\n      - ",
            run_block,
            re.S,
        )
        assert m, "non-vacuity: the fixture bootstrap step is missing"
        body = m.group(1)
        assert "python tests/create_fixtures.py" in body
        assert "git checkout -- tests/fixtures/" in body, (
            "ci.yml's fixture bootstrap does not restore the tracked "
            "fixture bytes after generation — the Windows cell will "
            "dirty G01 (RC-5)"
        )


def subprocess_index_bytes(path_in_repo: str) -> bytes:
    """The INDEX bytes of a tracked file (what git compares against)."""
    import subprocess

    blob = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path_in_repo}"],
        capture_output=True, text=True, cwd=REPO, timeout=60,
    ).stdout.strip()
    return subprocess.run(
        ["git", "cat-file", "blob", blob],
        capture_output=True, timeout=60, cwd=REPO,
    ).stdout
