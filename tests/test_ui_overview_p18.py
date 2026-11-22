"""P18-UI-S3a: Home / Fund overview redesign.

AppTest on freshly generated demo funds (the repo's own generator, no
network) for BOTH markets. Zero exceptions, mandatory banners, the new
NAV/total-return block, halt state, and the S4 consistency pin: the
fund value shown equals the ledger's last equity_after.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "src" / "niveshdristi" / "ui" / "app.py"


def _make_fund(base: Path, market: str, fund_id: str) -> None:
    """Run the repo's own demo-fund generator (offline, synthetic)."""
    import subprocess

    r = subprocess.run(
        [sys.executable, "tools/make_demo_fund.py", "--base", str(base),
         "--market", market, "--fund-id", fund_id],
        capture_output=True, text=True, cwd=str(REPO), timeout=600,
    )
    assert r.returncode == 0, r.stderr[-400:]


@pytest.fixture(scope="module")
def demo_base(tmp_path_factory):
    base = tmp_path_factory.mktemp("demo18")
    _make_fund(base, "IN_NSE", "p18_in_demo")
    _make_fund(base, "US_NYSE", "p18_us_demo")
    return base


def _run_app(base: Path, fund_id: str, page: str | None = None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP))
    at.session_state["fund_id"] = fund_id
    at.session_state["fund_base"] = str(base)
    at.run(timeout=300)
    assert not at.exception, at.exception
    if page:
        at.sidebar.radio[0].set_value(page).run(timeout=300)
        assert not at.exception, at.exception
    return at


def _texts(block):
    """Typed-accessor text collection (same approach as test_ui.py; the
    columns walk is two-level like the original to avoid recursion)."""
    out = []
    for attr in ("caption", "markdown", "metric", "error", "warning", "info",
                 "title", "subheader", "header", "json", "text", "table"):
        try:
            elements = getattr(block, attr)
        except (AttributeError, KeyError):
            continue
        for e in elements:
            label = getattr(e, "label", None)
            if label:
                out.append(str(label))
            out.append(str(getattr(e, "value", "")))
    try:
        cols = block.columns
    except (AttributeError, KeyError):
        cols = []
    for col_group in cols:
        for col in col_group:
            if col is not block:
                out.extend(_texts(col))
    return out


def _page_text(at) -> str:
    """Main-block texts PLUS the top-level banner accessors (warning/
    error/info live outside at.main)."""
    parts = [" ".join(_texts(at.main))]
    for accessor in ("warning", "error", "info", "success"):
        for el in getattr(at, accessor):
            parts.append(str(el.value))
    return " ".join(parts)


class TestHomeOverview:
    def test_in_demo_overview(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Overview")
        texts = _page_text(at)
        assert "DATA LIMITATIONS:" in texts
        assert "RATES UNVERIFIED" in texts
        assert "NOT investment advice" in texts
        assert "Fund overview" in texts
        assert "fund: p18_in_demo" in texts
        assert "IN_NSE" in texts or "India" in texts
        assert "Total return since start" in texts
        assert "pipeline demonstration only" in texts
        assert "kill-switch: not halted" in texts
        # st.line_chart records as a vega-lite chart element in AppTest
        assert any(getattr(el, "type", "") == "vega_lite_chart"
                   for el in at.main), "NAV line chart must render"
        # positions show the resolved synthetic name
        assert "Synthetic Co 090 (demo)" in texts or "SYN090" in texts

    def test_us_demo_overview_costs_banner(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Overview")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts, (
            "the US fund must carry the COSTS NOT MODELED banner"
        )
        assert "DATA LIMITATIONS:" in texts
        assert "Total return since start" in texts

    def test_numbers_equal_ledger(self, demo_base):
        """S4: the fund value on the page equals the ledger's last
        equity_after (raw float formatted)."""
        at = _run_app(demo_base, "p18_in_demo", "Overview")
        ledger = (demo_base / "p18_in_demo" / "ledger.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        last = json.loads(ledger[-1])
        equity = float(last["equity_after"])
        # the page formats INR money with the market's 3-2-2 grouping
        # (services.format.format_money_code)
        q = f"{equity:.2f}"
        whole, frac = q.split(".")
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        formatted = ",".join(groups + [tail]) + "." + frac
        assert formatted in _page_text(at), (
            f"ledger equity {formatted} must appear on the page"
        )


class TestWatchlist:
    def test_in_demo_watchlist(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Watchlist")
        texts = _page_text(at)
        assert "Watchlist" in texts
        assert "Synthetic Co 090 (demo)" in texts
        assert "SYN090" in texts
        assert "synthetic demo data" in texts
        assert "Last close" in texts
        assert "vs previous close" in texts

    def test_us_demo_watchlist(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Watchlist")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts
        assert "Synthetic Co 090 (demo)" in texts

    def test_watchlist_search_filter(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Watchlist")
        search = at.text_input[0]
        search.set_value("SYN091").run(timeout=300)
        assert not at.exception, at.exception
        texts = _page_text(at)
        assert "Synthetic Co 091 (demo)" in texts
        assert "Synthetic Co 090 (demo)" not in texts, (
            "the search filter must hide non-matching cards"
        )

    def test_watchlist_search_no_match(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Watchlist")
        at.text_input[0].set_value("ZZZZZ").run(timeout=300)
        texts = _page_text(at)
        assert "no symbol matches" in texts


class TestStockDetail:
    def test_in_demo_stock_detail(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Stock Detail")
        texts = _page_text(at)
        assert "Stock detail: Synthetic Co 090 (demo)" in texts
        assert "ticker: SYN090" in texts
        assert "synthetic demo data" in texts
        assert "Per-model signals" in texts
        assert "Recent orders for this symbol" in texts

    def test_us_demo_stock_detail(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Stock Detail")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts
        assert "Stock detail: Synthetic Co 090 (demo)" in texts


class TestHoldingsOrders:
    def test_in_demo_holdings(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Holdings")
        texts = _page_text(at)
        assert "Holdings" in texts
        # the holdings table renders as a dataframe element; the resolved
        # names inside it are verified at the resolver level (test_ui_names)
        assert any(getattr(el, "type", "") == "dataframe"
                   for el in at.main), "holdings table must render"
        # the table columns themselves are verified at the service level
        view_rows = at.dataframe[0].value
        assert "Weight" in getattr(view_rows, "columns", []), (
            "holdings table must carry a Weight column"
        )
        assert "* synthetic demo data" in texts
        assert "Total value" in texts
        # the honest n/a state lives in the P&L cells of the dataframe
        df_val = at.dataframe[0].value
        assert "n/a (no avg cost recorded)" in set(
            df_val["Unrealised P&L"]), (
            "avg_cost==0 rows must show the honest n/a state"
        )

    def test_us_demo_holdings_costs_banner(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Holdings")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts
        assert "Total value" in texts

    def test_orders_fills_and_filters(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Orders")
        texts = _page_text(at)
        assert "Orders / Activity" in texts
        assert "7 of 7 fill(s)" in texts
        assert any(getattr(el, "type", "") == "dataframe"
                   for el in at.main), "fills table must render"
        fill_rows = at.dataframe[0].value
        assert "Costs" in getattr(fill_rows, "columns", []), (
            "fills table must carry a Costs column"
        )
        costs_values = " | ".join(str(v) for v in fill_rows["Costs"])
        assert ("costs not modeled" in costs_values
                or "fees" in costs_values), costs_values
        # Pending content now lives in the "Pending" tab
        assert "target weight" in texts or "no pending gated orders" in texts
        # side filter
        at.selectbox[1].set_value("BUY").run(timeout=300)
        assert not at.exception, at.exception

    def test_us_orders_costs_not_modeled_state(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Orders")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts


class TestBacktestAndSettings:
    def test_backtest_lab_in(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Backtest Lab")
        texts = _page_text(at)
        assert "Backtest lab" in texts
        assert "pipeline demonstration" in texts
        assert "Run backtest" in [b.label for b in at.button]
        # run it and check the verdict + metrics render
        at.button[0].click().run(timeout=300)
        assert not at.exception, at.exception
        texts = _page_text(at)
        assert "not evidence of performance" in texts
        assert "drag (NAV bps)" in texts

    def test_backtest_lab_us(self, demo_base):
        at = _run_app(demo_base, "p18_us_demo", "Backtest Lab")
        texts = _page_text(at)
        assert "COSTS NOT MODELED" in texts
        at.button[0].click().run(timeout=300)
        assert not at.exception, at.exception

    def test_settings_about_and_guide(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Settings")
        texts = _page_text(at)
        assert "Settings (read-only)" in texts
        assert "About this data" in texts
        assert "How to read each page" in texts
        assert "synthetic demo data" in texts
        assert any(getattr(el, "type", "") == "dataframe"
                   for el in at.main), "page guide table must render"


class TestAllPagesSelfReview:
    """S5: every page, both funds — zero exceptions, and the ONLY st.warning
    is the intentional data-limitation banner."""

    @pytest.mark.parametrize(("fund_id", "expect_banner"), [
        ("p18_in_demo", False),
        ("p18_us_demo", True),
    ])
    def test_every_page_zero_exceptions(self, demo_base, fund_id,
                                        expect_banner):
        for page in ("Overview", "Watchlist", "Stock Detail", "Holdings",
                     "Orders", "Market Overview", "Deep-Dive",
                     "Backtest Lab", "Paper Fund", "Settings"):
            at = _run_app(demo_base, fund_id, page)
            assert not at.exception, f"{page}: {at.exception}"
            warnings = [w.value for w in at.warning]
            assert len(warnings) == 1, (
                f"{page}: unexpected warnings {warnings}"
            )
            assert "DATA LIMITATIONS:" in warnings[0]
            if expect_banner:
                assert "COSTS NOT MODELED" in warnings[0]


class TestWatchlistP19:
    def test_pills_and_sparklines(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Watchlist")
        # st.pills records as a button_group element in AppTest
        assert any(getattr(el, "type", "") == "button_group"
                   for el in at.main), "filter pills must render"
        assert any(getattr(el, "type", "") == "vega_lite_chart"
                   for el in at.main), "sparklines must render"
        # gainers pill keeps at least the synthetic cards
        pills = at.pills[0]
        pills.set_value("Gainers").run(timeout=300)
        assert not at.exception, at.exception

    def test_stockcard_keys_styled(self, demo_base):
        at = _run_app(demo_base, "p18_in_demo", "Watchlist")
        # keyed containers render as separate elements; the page must have
        # no exceptions and at least 2 stock cards worth of content
        texts = _page_text(at)
        assert texts.count("Synthetic Co 090 (demo)") >= 1
        assert "Synthetic Co 091 (demo)" in texts
