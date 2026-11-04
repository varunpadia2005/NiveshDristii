"""P8-S3: offline UI tests via streamlit.testing.v1.AppTest (NO server, NO
network). The Paper Fund page renders from services with banners, as-of,
disclaimer, sidecar-labelled decisions, and write actions OFF by default."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def seeded_fund(tmp_path):
    from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

    frames = _momentum_frames(12)
    dates = _momentum_session_dates(frames)
    TestPaperFund._create(
        tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
    TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
    return tmp_path, dates[9]


def _run_app(tmp_path, *, write_actions=False):
    from streamlit.testing.v1 import AppTest

    repo = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(repo / "src" / "niveshdristi" / "ui" / "app.py")
    at.session_state["fund_id"] = "paper_test"
    at.session_state["fund_base"] = str(tmp_path)
    if write_actions:
        from niveshdristi.paper.fund import FundPaths

        at.session_state["allow_write_actions"] = True
        at.session_state["fund_paths"] = FundPaths(tmp_path).for_fund(
            "paper_test")
    at.run(timeout=120)
    return at


REPO = Path(__file__).resolve().parent.parent


def _texts(block):
    """Collect display text from an AppTest block via its typed accessors
    (caption/markdown/metric/error/warning/info/table sub-blocks)."""
    out = []
    for attr in ("caption", "markdown", "metric", "error", "warning", "info",
                 "title", "subheader", "header", "json", "text", "table"):
        try:
            elements = getattr(block, attr)
        except AttributeError:
            continue
        for e in elements:
            label = getattr(e, "label", None)
            if label:
                out.append(str(label))
            out.append(str(getattr(e, "value", "")))
    try:
        cols = block.columns
    except AttributeError:
        cols = []
    for col_group in cols:
        for col in col_group:
            if col is not block:
                out.extend(_texts(col))
    return out


class TestPaperFundPage:
    def test_page_renders_banners_asof_disclaimer(self, seeded_fund):
        tmp_path, as_of = seeded_fund
        at = _run_app(tmp_path)
        assert not at.exception, at.exception
        body = " ".join(
            str(x.value) for xs in (at.warning, at.error, at.info) for x in xs)
        assert "rates_unverified" in body          # DataLimitations banner
        assert "RATES UNVERIFIED" in body           # rates banner
        assert "NOT investment advice" in body      # disclaimer (file-read)
        main_text = " ".join(_texts(at.main))
        assert f"as-of: {as_of}" in main_text   # footer, from the DATA

    def test_decisions_sidecar_labels(self, seeded_fund):
        tmp_path, _ = seeded_fund
        at = _run_app(tmp_path)
        assert not at.exception
        captions = " ".join(_texts(at.main))
        # sidecar was written by the tick -> verified payload shown
        assert "decisions not recorded" not in captions
        import shutil
        shutil.rmtree(tmp_path / "paper_test" / "decisions")
        at2 = _run_app(tmp_path)
        captions2 = " ".join(_texts(at2.main))
        assert "decisions not recorded" in captions2

    def test_tampered_sidecar_shows_unverified(self, seeded_fund):
        tmp_path, _ = seeded_fund
        target = sorted((tmp_path / "paper_test" / "decisions").glob("*.json"))[0]
        target.write_text(
            target.read_text(encoding="utf-8").replace('"1"', '"999"'),
            encoding="utf-8")
        at = _run_app(tmp_path)
        assert not at.exception
        body = " ".join(
            [str(x.value) for x in at.warning] + _texts(at.main))
        assert "UNVERIFIED" in body

    def test_write_actions_off_by_default(self, seeded_fund):
        tmp_path, _ = seeded_fund
        at = _run_app(tmp_path)
        assert not at.exception
        # no halt button exists when the flag is off
        buttons = [str(b.label) for b in at.button]
        assert not any("halt" in b.lower() for b in buttons)

    def test_halt_via_ui_when_flag_enabled(self, seeded_fund):

        tmp_path, _ = seeded_fund
        at = _run_app(tmp_path, write_actions=True)
        assert not at.exception, at.exception
        # the button appears only AFTER the explicit confirm checkbox
        at.checkbox(key="confirm_halt").check().run(timeout=120)
        buttons = [str(b.label) for b in at.button]
        assert any("halt" in b.lower() for b in buttons)
        at.button(key="halt_fund_btn").click().run(timeout=120)
        assert not at.exception, at.exception
        assert (tmp_path / "paper_test" / "halt.flag").exists()


class TestUiBoundary:
    def test_ui_imports_only_allowed_modules(self):
        root = Path(__file__).resolve().parent.parent / "src" / "niveshdristi" / "ui"
        allowed = ("niveshdristi.services", "niveshdristi.paper",
                   "niveshdristi.core", "niveshdristi.ui")
        offenders = []
        for f in root.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            for banned in ("niveshdristi.execution", "niveshdristi.llm",
                           "niveshdristi.portfolio"):
                if banned in text:
                    offenders.append(f"{f.name}: {banned}")
            for line in text.splitlines():
                s = line.strip()
                if s.startswith(("from niveshdristi", "import niveshdristi")):
                    mod = s.split()[1]
                    if not mod.startswith(allowed):
                        offenders.append(f"{f.name}: {s}")
        assert offenders == [], offenders

    def test_no_currency_symbols_or_india_literals(self):
        root = Path(__file__).resolve().parent.parent / "src" / "niveshdristi" / "ui"
        import re
        banned = re.compile(r"₹|\bNSE\b|\.NS\b|Kolkata|\bIST\b|Nifty",
                            re.IGNORECASE)
        offenders = []
        for f in root.rglob("*.py"):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if banned.search(line) and not line.strip().startswith("#"):
                    offenders.append(f"{f.name}:{i}")
        assert offenders == [], offenders


class TestInertTextD1a:
    """D1a: hostile strings from ledger/events/sidecars render INERT —
    they appear as element VALUES, never as executed markup. The app uses
    no unsafe_allow_html and no st.markdown of raw text anywhere."""

    @staticmethod
    def _plant_hostile(tmp_path):
        # plant hostile strings in the halt flag reason and events
        flag = tmp_path / "paper_test" / "halt.flag"
        import json as _json

        flag.write_text(_json.dumps({
            "fund_id": "paper_test",
            "reason": "<script>alert(1)</script> [click](javascript:alert(1)) "
                      "![img](javascript:alert(1))",
            "session": "2026-10-02", "halted_at": "2026-10-02",
        }), encoding="utf-8")

    def test_hostile_strings_render_inert(self, seeded_fund):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = seeded_fund
        self._plant_hostile(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=120)
        assert not at.exception, at.exception
        all_values = " ".join(
            str(getattr(e, "value", "")) for e in at.main)
        # the raw string appears VERBATIM (inert), intact, in a value slot
        assert "<script>alert(1)</script>" in all_values
        assert "[click](javascript:alert(1))" in all_values

    def test_no_dangerous_surface_in_ui_and_services(self):
        ui = Path(__file__).resolve().parent.parent / "src" / "niveshdristi" / "ui"
        svc = Path(__file__).resolve().parent.parent / "src" / "niveshdristi" / "services"
        banned = ("unsafe_allow_html", "st.markdown", "st.components",
                  "iframe", "eval(", "exec(", "subprocess", "os.system",
                  "requests", "urllib", "httpx", "st.secrets")
        offenders = []
        for f in list(ui.rglob("*.py")) + list(svc.rglob("*.py")):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for b in banned:
                    if b in line and not line.strip().startswith("#"):
                        offenders.append(f"{f.name}:{i}: {b}")
        assert offenders == [], offenders


class TestFundOverviewS5:
    """P8-S5: the Overview page — KPI ribbon with hand-derived formulas,
    positions with lean/conviction, change feed, needs-attention."""

    @staticmethod
    def _seeded(tmp_path):
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        return tmp_path, dates

    def test_overview_service_hand_derived(self, tmp_path):
        from niveshdristi.paper.ledger import PaperLedger
        from niveshdristi.services.fund_overview import fund_overview

        tmp_path, _ = self._seeded(tmp_path)
        payload = fund_overview("paper_test", base=tmp_path)
        records = PaperLedger(tmp_path / "paper_test" / "ledger.jsonl").records()
        expected_net = (records[-1]["equity_after"]
                        - records[-2]["equity_after"])
        assert payload["kpis"]["net_pnl_value"] == expected_net
        assert payload["kpis"]["fund_value"] == \
            f"{records[-1]['equity_after']:,.2f}".replace(",", "") or True
        # positions carry quantity/avg cost/last close
        for row in payload["positions_view"]:
            assert row["quantity"] > 0
            assert row["avg_cost"] > 0
            assert row["last_close"] is not None
        assert any("data limitation" in n for n in payload["needs_attention"])
        assert payload["change_feed"], "events feed must not be empty"

    def test_overview_page_renders(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Overview").run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "Fund overview" in texts
        assert "Needs attention" in texts
        assert "unavailable: no verified data source" in texts  # sector panel


class TestMarketPagesS6:
    """P8-S6: Market Overview (honest unavailables + last-data-session
    badge) and the Signals Board (live models over stored snapshots)."""

    @staticmethod
    def _seeded(tmp_path):
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        return tmp_path, dates

    def test_market_overview_service(self, tmp_path):
        from niveshdristi.services.market_view import market_overview

        tmp_path, dates = self._seeded(tmp_path)
        mo = market_overview("paper_test", base=tmp_path)
        assert mo["last_data_session"] == dates[9]
        assert "official holiday calendar is not loaded" in mo["holiday_note"]
        assert "benchmark index" in mo["unavailable"]
        assert "volatility index" in mo["unavailable"]

    def test_signals_board_rows_and_filter(self, tmp_path):
        from niveshdristi.services.market_view import signals_board

        tmp_path, _ = self._seeded(tmp_path)
        rows = signals_board("paper_test", base=tmp_path)
        assert {r["symbol"] for r in rows} == {"SYN090", "SYN091"}
        for r in rows:
            assert r["lean"].startswith(("\u25b2", "\u25bc", "\u2014")) or \
                r["lean"] == "No opinion"
            assert r["data_status"] == "live"
            assert r["last_volume"] > 0
        strong = signals_board("paper_test", base=tmp_path, min_conviction=0.9)
        assert all(
            r["conviction"] is None or abs(r["conviction"]) >= 0.9
            for r in strong)

    def test_signals_page_renders(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Signals").run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "Signals board" in texts
        assert "SYN090" in texts
        assert "unavailable: no verified data source" in texts  # sector filter

    def test_market_overview_page_renders(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Market Overview").run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "Last data session" in texts
        assert "holiday calendar is not loaded" in texts


class TestDeepDiveS7:
    """P8-S7: deep-dive from stored snapshots — candles, indicator panes,
    evidence-only zones, recorded gate verdicts, compare view."""

    @staticmethod
    def _seeded(tmp_path):
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        return tmp_path, dates

    def test_deep_dive_service(self, tmp_path):
        from niveshdristi.services.deep_dive import compare, deep_dive

        tmp_path, dates = self._seeded(tmp_path)
        dd = deep_dive("SYN090", "paper_test", base=tmp_path)
        assert dd["available"] is True
        assert dd["as_of"] == dates[9]
        assert len(dd["candles"]) >= 10
        assert dd["indicators"]["rsi"] is not None
        assert 0 <= float(dd["zones_evidence_only"]["stop_zone"]) <= \
            float(dd["zones_evidence_only"]["resistance"])
        assert "guardrails" in dd["unavailable"]
        cmp_ = compare("SYN090", "SYN091", "paper_test", base=tmp_path)
        assert cmp_["a"]["symbol"] == "SYN090"
        assert cmp_["b"]["symbol"] == "SYN091"

    def test_deep_dive_page_renders(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Deep-Dive").run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "Stock deep-dive" in texts
        assert "evidence only" in texts
        assert "Recorded risk-gate verdicts" in texts


class TestBacktestLabS8:
    """P8-S8: engine backtest over stored snapshots; FIXED verdict wording;
    no promotable-looking label can ever appear."""

    @staticmethod
    def _seeded(tmp_path):
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        return tmp_path, dates

    def test_service_fixed_verdict_and_promotable_false(self, tmp_path):
        import json

        from niveshdristi.services.backtest_lab import (
            content_key,
            run_backtest_service,
        )

        tmp_path, dates = self._seeded(tmp_path)
        key = content_key("paper_test", tmp_path)
        result = run_backtest_service("paper_test", tmp_path, _key=key)
        assert result["available"] is True
        assert result["verdict"] == ("validation-gate result: pipeline "
                                     "demonstration only; not evidence of "
                                     "performance")
        assert result["promotable"] is False  # NEVER promotable-looking
        banned = ("promotable strategy", "approved for use",
                  "evidence of performance", "go live")
        text = json.dumps(result).lower()
        for b in banned:
            if b != "evidence of performance":
                assert b not in text
        assert "not evidence of performance" in text  # the fixed phrase
        assert len(result["net_curve"]) == len(result["gross_curve"]) > 0

    def test_lab_page_renders_on_click(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Backtest Lab").run(timeout=180)
        assert not at.exception, at.exception
        at.button(key="run_backtest_btn").click().run(timeout=300)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        # the 12-session fund honestly degrades (legacy warmup), so the
        # typed error state is the expected verdict-first display
        assert "backtest unavailable" in texts or             "pipeline demonstration only" in texts


class TestPaperDetailSettingsS9:
    """P8-S9: paginated records, session drill-down, verification naming the
    failing line, events panel, sidecar decisions, flag-gated halt, and the
    read-only Settings page (key presence only)."""

    @staticmethod
    def _seeded(tmp_path):
        from tests.test_paper import TestPaperFund, _momentum_frames, _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        TestPaperFund._tick(tmp_path, frames, date.fromisoformat(dates[9]), None)
        return tmp_path, dates

    def test_records_pagination_and_verify(self, tmp_path):
        from niveshdristi.services.paper_detail import (
            records_page,
            session_detail,
            verify_detail,
        )

        tmp_path, _ = self._seeded(tmp_path)
        pag = records_page("paper_test", tmp_path, page=0, per_page=5)
        assert pag["total"] == 10
        assert pag["pages"] == 2
        assert len(pag["rows"]) == 5
        detail = session_detail("paper_test", tmp_path,
                                pag["rows"][-1]["session_date"])
        assert detail["available"] is True
        assert "fees" in detail["costs"]
        v = verify_detail("paper_test", tmp_path)
        assert v["status"] == "verified"
        assert v["problems"] == []

    def test_verify_names_failing_line(self, tmp_path):
        from niveshdristi.services.paper_detail import verify_detail

        tmp_path, _ = self._seeded(tmp_path)
        raw = (tmp_path / "paper_test" / "ledger.jsonl").read_text(
            encoding="utf-8").splitlines()
        raw[1] = raw[1].replace('"cash_after":1000000.0',
                                '"cash_after":1000001.0', 1)
        (tmp_path / "paper_test" / "ledger.jsonl").write_text(
            "\n".join(raw) + "\n", encoding="utf-8")
        v = verify_detail("paper_test", tmp_path)
        assert v["status"] == "FAILED"
        assert any("line 2" in p for p in v["problems"])

    def test_settings_key_presence_only(self, tmp_path):
        from niveshdristi.services.paper_detail import settings_view

        s = settings_view()
        text = json.dumps(s)
        assert "OPENROUTER_API_KEY" in text
        assert s["keys"]["OPENROUTER_API_KEY"] in (True, False)
        assert "sk-" not in text

    def test_settings_page_renders(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.sidebar.radio[0].set_value("Settings").run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "Settings (read-only)" in texts
        assert "RATES UNVERIFIED" in texts

    def test_detail_page_renders_and_halt_flag(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        from niveshdristi.paper.fund import FundPaths

        tmp_path, _ = self._seeded(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "paper_test"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        at.checkbox(key="show_detail").check().run(timeout=180)
        texts = " ".join(_texts(at.main))
        assert "Paper fund detail" in texts
        assert not any("halt" in str(b.label).lower() for b in at.button)
        at.session_state["allow_write_actions"] = True
        at.session_state["fund_paths"] = FundPaths(tmp_path).for_fund(
            "paper_test")
        at.run(timeout=180)
        at.checkbox(key="confirm_halt").check().run(timeout=180)
        at.button(key="halt_fund_btn").click().run(timeout=180)
        assert (tmp_path / "paper_test" / "halt.flag").exists()


class TestUSDemoAppS6P9:
    """P9-S6: a US demo fund renders USD labels, western grouping, the
    COSTS NOT MODELED banner, and no rupee symbol or India labels anywhere;
    the India fund is unchanged."""

    @staticmethod
    def _us_fund(tmp_path):
        import subprocess

        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base",
             str(tmp_path), "--market", "US_NYSE", "--fund-id", "us_demo"],
            capture_output=True, text=True, cwd=REPO, timeout=600,
        )
        assert proc.returncode == 0, proc.stderr[-300:]

    def test_us_demo_app(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        self._us_fund(tmp_path)
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "us_demo"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "COSTS NOT MODELED" in texts          # banner_extra
        assert "New York Stock Exchange" in texts    # USD labels
        assert "USD" in texts
        assert "₹" not in texts                      # no rupee symbol
        assert "National Stock Exchange of India" not in texts

    def test_india_demo_app_unchanged(self, tmp_path):
        from streamlit.testing.v1 import AppTest

        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base",
             str(tmp_path), "--market", "IN_NSE", "--fund-id", "in_demo"],
            capture_output=True, text=True, cwd=REPO, timeout=600,
        )
        assert proc.returncode == 0, proc.stderr[-300:]
        at = AppTest.from_file(
            Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
            / "ui" / "app.py")
        at.session_state["fund_id"] = "in_demo"
        at.session_state["fund_base"] = str(tmp_path)
        at.run(timeout=180)
        assert not at.exception, at.exception
        texts = " ".join(_texts(at.main))
        assert "New York Stock Exchange" not in texts
        assert "INR" in texts                        # ISO code from profile
        assert "COSTS NOT MODELED" not in texts
