"""P8-S3: offline UI tests via streamlit.testing.v1.AppTest (NO server, NO
network). The Paper Fund page renders from services with banners, as-of,
disclaimer, sidecar-labelled decisions, and write actions OFF by default."""

from __future__ import annotations

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
