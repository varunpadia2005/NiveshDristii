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
    "niveshdristi.alpha",      # read-only registered models (S5/S6 display)
    "niveshdristi.marketdata",  # as-of limited data handle (read-only)
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



class TestFormattingVocabularyCacheF_S4:
    """P8-S4: formatting known answers, binding vocabulary, cache counter."""

    def test_format_money_known_answers(self):
        from datetime import date

        from niveshdristi.markets import IN_NSE_PROFILE
        from niveshdristi.services.format import (
            format_compact,
            format_date,
            format_money,
            format_pct,
        )

        P = IN_NSE_PROFILE
        assert format_money(1234567.89, P) == "12,34,567.89"
        assert format_money(100000, P) == "1,00,000.00"
        assert format_money(12345, P) == "12,345.00"
        assert format_money(999, P) == "999.00"
        assert format_money(-1234567.89, P) == "-12,34,567.89"
        assert format_money(0, P) == "0.00"
        assert format_compact(25000000, P) == "2.50 crore"
        assert format_compact(250000, P) == "2.50 lakh"
        assert format_compact(1234567.89, P) == "12.35 lakh"
        assert format_compact(999, P) == "999.00"
        assert format_compact(-250000, P) == "-2.50 lakh"
        assert format_pct(0.0523) == "5.2%"
        assert format_pct(0.0) == "0.0%"
        assert format_pct(-0.031) == "-3.1%"
        assert format_pct(1.0) == "100.0%"
        assert format_date("2026-10-30T15:30:00") == "2026-10-30"
        assert format_date(date(2026, 10, 30)) == "2026-10-30"

    def test_western_profile_grouping(self):
        from niveshdristi.services.format import format_money

        class Western:
            digit_grouping = "western"

        assert format_money(1234567.89, Western()) == "1,234,567.89"

    def test_vocabulary_labels_and_thresholds(self):
        from niveshdristi.services.vocabulary import (
            CONVICTION_CAPTION,
            lean_label,
        )

        assert lean_label(0.5) == "\u25b2 Positive lean"
        assert lean_label(0.2) == "\u25b2 Positive lean"      # >= threshold
        assert lean_label(-0.5) == "\u25bc Negative lean"
        assert lean_label(-0.2) == "\u25bc Negative lean"     # <= threshold
        assert lean_label(0.0) == "\u2014 Neutral"
        assert lean_label(0.19) == "\u2014 Neutral"
        assert lean_label(None) == "No opinion"
        assert CONVICTION_CAPTION == "Conviction (uncalibrated, -1 to +1)"

    def test_labels_never_use_advice_verbs(self):
        """BINDING: no label output contains buy/sell/hold/swap/recommend/
        advice (case-insensitive substring grep over ALL vocabulary outputs
        and their qualifiers)."""
        from niveshdristi.services.vocabulary import (
            CONVICTION_CAPTION,
            lean_label,
            model_status_label,
            negative_qualifier,
        )

        banned = ("buy", "sell", "hold", "swap", "recommend", "advice")
        outputs = [lean_label(c) for c in
                   (-1.0, -0.5, -0.2, -0.1, 0.0, 0.1, 0.2, 0.5, 1.0, None)]
        outputs += [negative_qualifier(long_only=b, held=h)
                    for b in (True, False) for h in (True, False)]
        outputs += [model_status_label(type("M", (), {"data_status": s})())
                    for s in ("stub", "evidence_only", "live")]
        outputs.append(CONVICTION_CAPTION)
        for text in outputs:
            low = text.lower()
            for word in banned:
                assert word not in low, (text, word)

    def test_cache_hit_makes_zero_recomputation(self, tmp_path):
        from datetime import date, timedelta

        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)

        from niveshdristi.services import cache as svc_cache

        svc_cache.reset_cached_call_count()
        key = svc_cache.ledger_cache_key("paper_test", tmp_path)
        svc_cache.cached_read_fund("paper_test", tmp_path, key)
        first = svc_cache.cached_call_count()
        svc_cache.cached_read_fund("paper_test", tmp_path, key)
        second = svc_cache.cached_call_count()
        assert first == 1
        assert second == 1  # ZERO recomputation on the second render
