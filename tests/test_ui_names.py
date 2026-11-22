"""P18-UI-S2: display-name resolver tests.

Non-vacuity: at least 5 symbols resolved across IN/US demo funds and
unknown symbols. Mutation: a resolver that returns blank must FAIL.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestDisplayName:
    def test_synthetic_pattern(self):
        from niveshdristi.ui.names import display_name, display_tag

        assert display_name("SYN090") == "Synthetic Co 090 (demo)"
        assert display_name("SYN0091") == "Synthetic Co 091 (demo)"
        assert display_tag("SYN090") == "synthetic demo data"
        assert display_tag("RELIANCE") == ""

    def test_real_ticker_falls_back_to_itself(self):
        from niveshdristi.ui.names import display_name

        assert display_name("RELIANCE") == "RELIANCE"
        assert display_name("AAPL") == "AAPL"

    def test_unknown_and_empty_symbols(self):
        from niveshdristi.ui.names import display_name

        assert display_name("") == ""
        assert display_name("  SYN090  ") == "Synthetic Co 090 (demo)"
        assert display_name("weird-1") == "weird-1"

    def test_non_vacuity_across_demo_funds(self, tmp_path):
        """At least 5 distinct symbols resolve across freshly generated IN
        + US demo funds (the repo's own generator) and the tracked
        universes. No dependence on any local demo folder."""
        import glob
        import json
        import subprocess

        from niveshdristi.ui.names import display_name

        symbols: set[str] = set()
        for market, fund in (("IN_NSE", "p18_in_names"),
                             ("US_NYSE", "p18_us_names")):
            r = subprocess.run(
                [sys.executable, "tools/make_demo_fund.py", "--base",
                 str(tmp_path), "--market", market, "--fund-id", fund],
                capture_output=True, text=True, cwd=str(REPO), timeout=600,
            )
            assert r.returncode == 0, r.stderr[-300:]
            ledger = (tmp_path / fund / "ledger.jsonl").read_text(
                encoding="utf-8")
            for line in ledger.splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                for p in rec.get("positions_after", []):
                    symbols.add(p["instrument"]["symbol"])
        for u in glob.glob(str(REPO / "universes" / "*.yaml")):
            for line in Path(u).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith('- "'):
                    symbols.add(line.strip('- "').strip())
        resolved = {display_name(s) for s in symbols}
        assert len(resolved) >= 5, (
            f"non-vacuity: only {len(resolved)} symbols resolved"
        )
        assert "Synthetic Co 090 (demo)" in resolved


class TestComparePayloadA3:
    def test_compare_payload_carries_banners(self, tmp_path):
        """A3 RED: render_compare called banner_strip(payload) on the
        compare result, which lacked 'disclaimer' -> KeyError. The service
        must provide the banner fields itself. Uses a freshly generated
        demo fund (no local-folder dependence)."""
        import subprocess

        from niveshdristi.services.deep_dive import compare

        r = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base",
             str(tmp_path), "--market", "IN_NSE", "--fund-id", "a3cmp"],
            capture_output=True, text=True, cwd=str(REPO), timeout=600,
        )
        assert r.returncode == 0, r.stderr[-300:]
        result = compare("SYN090", "SYN091", "a3cmp", base=str(tmp_path))
        for key in ("banner", "rates_banner", "disclaimer"):
            assert key in result, f"compare payload lacks {key!r}"
