"""P9-S1: seam tests — no hard-coded market ids in services/tools; alpha
models take currency from the context (registry lookup, XXX fallback)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestSeamsP9S1:
    def test_no_test_market_literal_in_services_or_tools(self):
        offenders = []
        for d in ("src/niveshdristi/services", "tools"):
            for f in (REPO / d).rglob("*.py"):
                if "TEST_M" in f.read_text(encoding="utf-8"):
                    offenders.append(str(f.relative_to(REPO)))
        assert offenders == [], offenders

    def test_currency_lookup_registry_and_fallback(self):
        sys.path.insert(0, str(REPO / "src"))
        from niveshdristi.alpha.currency import (
            PLACEHOLDER_CURRENCY,
            currency_for_market,
        )

        assert currency_for_market("IN_NSE") == "INR"
        assert currency_for_market("TEST_M") == PLACEHOLDER_CURRENCY
        assert currency_for_market("") == PLACEHOLDER_CURRENCY

    def test_alpha_has_no_currency_literal(self):
        offenders = []
        for f in (REPO / "src" / "niveshdristi" / "alpha" / "quant").rglob("*.py"):
            if 'currency="XXX"' in f.read_text(encoding="utf-8"):
                offenders.append(f.name)
        assert offenders == [], offenders

    def test_services_rules_from_header(self, tmp_path):
        from datetime import date, timedelta

        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        from niveshdristi.services.rules import (
            market_id_from_header,
            rules_from_header,
        )

        rules = rules_from_header("paper_test", tmp_path)
        assert rules.market_id == "TEST_M"  # the TEST harness created it so
        assert market_id_from_header("paper_test", tmp_path) == "TEST_M"

    def test_demo_generator_uses_profile_market(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO, timeout=600,
        )
        assert proc.returncode == 0, proc.stderr[-300:]
        header = json.loads(
            (tmp_path / "demo_synthetic" / "ledger.jsonl")
            .read_text(encoding="utf-8").splitlines()[0])
        rules = json.loads(header["market_rules_digest"])
        assert rules["market_id"] == "IN_NSE"


class TestCurrencyTableSync:
    """The alpha-owned currency table must agree with the markets registry
    (alpha cannot import markets; the TEST is the sync point)."""

    def test_table_matches_registry(self):
        sys.path.insert(0, str(REPO / "src"))
        from niveshdristi.alpha.currency import MARKET_CURRENCIES
        from niveshdristi.markets.registry import get_registry

        registry = get_registry()
        # every REGISTERED profile's currency is represented (US_NYSE is
        # pre-declared and registered in P9-S2)
        for market_id, profile in registry._profiles.items():  # noqa: SLF001
            assert MARKET_CURRENCIES.get(market_id) == profile.currency, (
                market_id)
        assert MARKET_CURRENCIES["IN_NSE"] == "INR"
