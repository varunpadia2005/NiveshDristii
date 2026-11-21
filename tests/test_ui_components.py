"""P18-UI-S1: design-system components.

Pure-function checks (formatting) + AppTest checks for the widget
components, on a synthetic IN demo fund. The mandatory-banner wording is
pinned by tests/test_ui.py already; here we add the component-level
non-vacuity and formatting pins.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# A minimal app script that exercises the S1 components. Written to tmp_path
# at test time (never inside the repo).
APP_SCRIPT = '''
import sys
sys.path.insert(0, r"{repo_src}")
from niveshdristi.ui import components

components.section_header("Section A", "caption text")
components.stock_card(name="Synthetic Co 090 (demo)", ticker="SYN090",
                      tags=["IN_NSE", "synthetic demo data"],
                      metric_label="Last close",
                      metric_value=components.fmt_money(130.94, "INR"),
                      caption="evidence only")
components.change_chip(12.5, "INR")
components.change_chip(-3.25, "INR")
components.change_chip(0.0, "INR")
components.change_chip(None)
components.metric_tile(label="Cash", value="99.52 INR", caption="from ledger")
components.empty_state("no stored data", "open Watchlist and pick a symbol")
components.fmt_pct  # attribute presence
'''


@pytest.fixture
def component_app(tmp_path):
    script = tmp_path / "component_app.py"
    script.write_text(
        APP_SCRIPT.format(repo_src=str(REPO / "src")), encoding="utf-8")
    return script


class TestFmtHelpers:
    def test_fmt_money_separators_and_code(self):
        from niveshdristi.ui.components import fmt_money

        assert fmt_money(1010615.34, "INR") == "1,010,615.34 INR"
        assert fmt_money(99.52, "USD") == "99.52 USD"
        assert fmt_money(None) == "—"
        assert fmt_money(5.0) == "5.00"

    def test_fmt_pct_signed(self):
        from niveshdristi.ui.components import fmt_pct

        assert fmt_pct(1.5) == "+1.50%"
        assert fmt_pct(-2.25) == "-2.25%"
        assert fmt_pct(None) == "—"

    def test_no_currency_symbol_literals_in_ui(self):
        """Non-vacuity companion of the guard test: the new helpers must not
        introduce symbol literals (the existing guard test scans for them)."""
        import re

        text = (REPO / "src" / "niveshdristi" / "ui" / "components.py").read_text(
            encoding="utf-8")
        assert not re.search(r"₹|\bNSE\b|\.NS\b|Nifty", text)


class TestComponentApp:
    def test_components_render_without_exception(self, component_app):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(component_app))
        at.run(timeout=120)
        assert not at.exception, at.exception
        body = " ".join(str(getattr(e, "value", "")) for e in at.main)
        assert "Synthetic Co 090 (demo)" in body
        assert "SYN090" in body
        assert "synthetic demo data" in body
        assert "1,010,615.34" in body or "130.94" in body
        assert "no stored data" in body
        assert "Next: open Watchlist" in body

    def test_change_chip_word_present_not_colour_alone(self, component_app):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(component_app))
        at.run(timeout=120)
        assert not at.exception, at.exception
        body = " ".join(str(getattr(e, "value", "")) for e in at.main)
        for word in ("up vs previous close", "down vs previous close",
                     "flat vs previous close", "no change data"):
            assert word in body, word
