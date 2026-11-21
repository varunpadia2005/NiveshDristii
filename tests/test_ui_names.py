"""P18-UI-S2: display-name resolver tests.

Non-vacuity: at least 5 symbols resolved across IN/US demo funds and
unknown symbols. Mutation: a resolver that returns blank must FAIL.
"""

from __future__ import annotations

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

    def test_non_vacuity_across_demo_funds(self):
        """At least 5 distinct symbols resolve through the real demo funds
        (IN + US) and the tracked universes."""
        import glob
        import json

        from niveshdristi.ui.names import display_name

        symbols: set[str] = set()
        for fund in ("demo_synthetic", "us_demo_synthetic"):
            ledger = (Path("D:/Nivesh Dristi/demo_session") / fund
                      / "ledger.jsonl")
            if not ledger.exists():  # pragma: no cover - demo data present
                continue
            for line in ledger.read_text(encoding="utf-8").splitlines():
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
