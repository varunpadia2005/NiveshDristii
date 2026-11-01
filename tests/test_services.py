"""P8-S1: services/ import boundary (NEW).

ALLOW: core/, paper/, markets/, engine/ (read-only results), stdlib, pydantic.
DENY: execution/ (brokers, orders), portfolio/ (targets/gates), llm/, ui/.
Fail-proofs: a planted forbidden import IS detected; the scans are
non-vacuous (they cover real files).
"""

from __future__ import annotations

from pathlib import Path

SERVICES_DENY = (
    "niveshdristi.execution",
    "niveshdristi.portfolio",
    "niveshdristi.llm",
    "niveshdristi.ui",
)
SERVICES_ALLOW = (
    "niveshdristi.core",
    "niveshdristi.paper",
    "niveshdristi.markets",
    "niveshdristi.engine",
    "niveshdristi.services",
)


def _pkg_root() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "niveshdristi"


class TestServicesBoundary:
    def test_no_forbidden_imports(self):
        offenders = []
        for f in (_pkg_root() / "services").rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            for banned in SERVICES_DENY:
                if banned in text:
                    offenders.append(f"{f.name}: {banned}")
        assert offenders == [], offenders

    def test_fail_proof_planted_forbidden_import_detected(self, tmp_path):
        """NON-VACUITY: the scanner catches a planted forbidden import."""
        probe = tmp_path / "services_probe"
        probe.mkdir()
        (probe / "bad.py").write_text(
            "from niveshdristi.execution.sim_broker import SimBroker\n",
            encoding="utf-8")
        offenders = []
        for f in probe.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            for banned in SERVICES_DENY:
                if banned in text:
                    offenders.append(f"{f.name}: {banned}")
        assert offenders, "fail-proof failed: planted import NOT detected"

    def test_only_allowed_niveshdristi_imports(self):
        offenders = []
        for f in (_pkg_root() / "services").rglob("*.py"):
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith(("from niveshdristi", "import niveshdristi")):
                    mod = s.split()[1]
                    if not mod.startswith(SERVICES_ALLOW):
                        offenders.append(f"{f.name}: {s}")
        assert offenders == [], offenders

    def test_scan_non_vacuous(self):
        files = list((_pkg_root() / "services").rglob("*.py"))
        assert len(files) >= 2  # __init__ + fund + labels

    def test_read_fund_payload_shape(self, tmp_path):
        from niveshdristi.services import market_labels, read_fund
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        from datetime import date, timedelta

        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames,
                            date.fromisoformat(dates[9]), None)
        payload = read_fund("paper_test", base=tmp_path)
        assert payload["as_of"] == dates[9]          # from the DATA
        assert payload["banner"]
        assert "rates_unverified" in payload["banner"]
        assert payload["rates_banner"] == "RATES UNVERIFIED"
        assert payload["verify"] == "verified"
        assert payload["halted"] is False
        assert payload["disclaimer"].startswith("NiveshDristi")
        assert "NOT investment advice" in payload["disclaimer"]
        assert payload["decisions"]["status"] in (
            "verified", "decisions not recorded", "unverified")
        labels = market_labels()
        assert labels["currency_code"] == "INR"  # ISO code, not a symbol
        assert labels["market_id"] == "IN_NSE"

