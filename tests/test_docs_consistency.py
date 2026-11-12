"""P11-S3: docs-vs-code consistency guards (NEW).

These tests fail when PROGRESS.md's historical statements drift out of
sync with the code they describe. They read tracked files only; no
network, no writes.

S3 items guarded here:
- `nd backtest run` was implemented in P10-S3 (cli/main.py backtest_run);
  PROGRESS.md's Phase 7-closure note still listed it among the
  not_implemented stubs — the consistency guard pins the correction.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class TestDocsConsistency:
    def test_backtest_run_implemented_and_not_documented_as_stub(self):
        """The CLI implements `nd backtest run` (P10-S3); PROGRESS.md must
        not keep listing it among the not_implemented stub commands."""
        cli_src = _read("src/niveshdristi/cli/main.py")
        assert '@backtest_app.command("run")' in cli_src, (
            "the test's premise changed: nd backtest run is no longer "
            "implemented in cli/main.py — update this guard"
        )
        progress = _read("docs/PROGRESS.md")
        # The stale bullet's LIVE-status opener (a historical QUOTE of the
        # old text is allowed; asserting the status quo again is not):
        stale_status = "(status quo, no change made): `nd data fetch`"
        assert stale_status not in progress, (
            "PROGRESS.md still claims (status quo, no change made) that "
            "`nd backtest run` is a not_implemented stub; it was "
            "implemented in P10-S3"
        )
        assert "implemented P10-S3" in progress, (
            "PROGRESS.md should record that nd backtest run was "
            "implemented P10-S3 (cli/main.py backtest_run)"
        )

    def test_phase_numbering_mapping_present(self):
        """CHANGELOG's phase numbers are offset by one vs PROGRESS.md for
        the paper-fund and UI phases; the mapping note must exist."""
        progress = _read("docs/PROGRESS.md")
        assert "Phase numbering" in progress, (
            "PROGRESS.md lacks the CHANGELOG-to-PROGRESS phase numbering "
            "mapping note (audit finding)"
        )
