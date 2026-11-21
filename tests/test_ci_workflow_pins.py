"""P11-A4-S2: every GitHub Actions workflow must pin actions by 40-hex SHA.

Fails if any file under .github/workflows/ contains a "{SHA:" placeholder,
any `uses:` that is not pinned to a full 40-hex commit SHA, or any pinned
`uses:` lacking a trailing "# vX.Y.Z" version comment. Local actions
("./...") are exempt. Deterministic, offline, read-only.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)(?:\s*#\s*(v\d+(?:\.\d+){0,2}))?\s*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert files, "non-vacuity: no workflow files found under .github/workflows/"
    return files


class TestCiWorkflowPins:
    def test_all_uses_lines_pinned_to_40hex_sha_with_version_comment(self):
        files = _workflow_files()
        uses_seen = 0
        failures: list[str] = []
        for wf in files:
            text = wf.read_text(encoding="utf-8")
            rel = wf.relative_to(REPO).as_posix()
            if "{SHA:" in text:
                for i, line in enumerate(text.splitlines(), 1):
                    if "{SHA:" in line:
                        failures.append(f"{rel}:{i}: contains a {{SHA: placeholder")
            for i, line in enumerate(text.splitlines(), 1):
                m = USES_RE.match(line)
                if not m:
                    continue
                uses_seen += 1
                ref, comment = m.group(1), m.group(2)
                if ref.startswith("./"):
                    continue  # local actions are exempt
                if "@" not in ref:
                    failures.append(f"{rel}:{i}: `uses: {ref}` has no ref at all")
                    continue
                name, _, pin = ref.rpartition("@")
                if not SHA_RE.fullmatch(pin):
                    failures.append(
                        f"{rel}:{i}: `uses: {ref}` is not pinned to a "
                        "40-hex commit SHA"
                    )
                if not comment:
                    failures.append(
                        f"{rel}:{i}: `uses: {ref}` lacks a trailing "
                        '"# vX.Y.Z" version comment'
                    )
        assert uses_seen > 0, "non-vacuity: no `uses:` lines found at all"
        assert not failures, "unpinned or unversioned actions:\n" + "\n".join(
            failures
        )


class TestCiJobLevelEnvNoRunnerContext:
    """P16-A-6 (15-V S0d escape): `runner` is NOT available in
    `jobs.<job_id>.env` — GitHub Actions only exposes it inside steps.
    P11-A11 shipped exactly this (job-level PYTHONPYCACHEPREFIX with
    ${{ runner.temp }}) and CI failed with a workflow STARTUP failure
    (all jobs lost, no logs). No guard test existed; the 15-V mutation
    re-adding job-level ${{ runner.temp }} escaped the suite. Pin:
    no job-level env value may reference runner.* contexts."""

    def test_no_job_level_env_uses_runner_context(self):
        import yaml

        failures: list[str] = []
        jobs_seen = 0
        for wf in _workflow_files():
            data = yaml.safe_load(wf.read_text(encoding="utf-8"))
            rel = wf.relative_to(REPO).as_posix()
            for job_id, job in (data or {}).get("jobs", {}).items():
                jobs_seen += 1
                env = (job or {}).get("env")
                if not env:
                    continue
                rendered = str(env)
                if "${{ runner." in rendered:
                    failures.append(
                        f"{rel}: job '{job_id}' env references runner.* "
                        f"(values: {env!r}) — the runner context is not "
                        "available at job level and the workflow fails to "
                        "start (P11-A11 incident)"
                    )
        assert jobs_seen > 0, "non-vacuity: no jobs found in any workflow"
        assert not failures, "\n".join(failures)
