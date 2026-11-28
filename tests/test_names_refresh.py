"""P21-NAMES S2: refresh command tests — fake HTTP only, no network.

Covers: success write (atomic files + meta), 403 typed error keeping
the old file, HTML-instead-of-CSV typed error, truncated file tripping
the sanity check (old file kept), dry-run writing nothing, status with
nothing stored. Mutation target: removing the sanity check must FAIL
test_truncated_file_keeps_old.
"""

from __future__ import annotations

import json

import pytest

from niveshdristi.names.refresh import (
    NamesRefreshError,
    refresh,
    status,
)

NSE_GOOD = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, "
    "MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    + "".join(
        f"SYM{i:04d},Company {i} Limited,EQ,01-JAN-2020,10,1,"
        f"INE{i:05d}01018,10\n" for i in range(1200)))

NSE_TRUNCATED = NSE_GOOD[:300]  # header + ~2 rows

BSE_BLOCKED_HTML = "<html><body>Access Denied</body></html>"


def _fake_fetch_factory(pages: dict[str, str]):
    def fake_fetch(url: str) -> str:
        for key, text in pages.items():
            if key in url:
                return text
        raise NamesRefreshError(f"unexpected url {url}")
    return fake_fetch


class TestRefresh:
    def test_success_writes_files_atomically(self, tmp_path):
        report = refresh(
            tmp_path, source="nse",
            fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
            now="2026-11-28T00:00:00+00:00")
        assert report["merged_total"] == 1200
        assert report["sources"]["NSE"]["rows"] == 1200
        csv_text = (tmp_path / "company_names.csv").read_text(
            encoding="utf-8")
        assert csv_text.startswith("ticker,name,exchange,isin,source,"
                                   "retrieved_at,bse_code\n")
        assert "SYM0000,Company 0 Limited,NSE" in csv_text
        assert ".tmp" not in " ".join(p.name for p in tmp_path.iterdir())
        meta = json.loads((tmp_path / "names_meta.json").read_text(
            encoding="utf-8"))
        assert meta["merged_total"] == 1200
        assert meta["retrieved_at"] == "2026-11-28T00:00:00+00:00"
        assert "sha256" in meta

    def test_bse_blocked_reported_nse_still_stored(self, tmp_path):
        report = refresh(
            tmp_path, source="all",
            fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD,
                                         "bseindia": BSE_BLOCKED_HTML}),
            now="2026-11-28T00:00:00+00:00")
        assert report["merged_total"] == 1200
        assert report["sources"]["BSE"]["rows"] == 0
        assert "BSE NOT AVAILABLE" in report["sources"]["BSE"]["error"]

    def test_http_error_keeps_old_file(self, tmp_path):
        # seed a good stored file first
        refresh(tmp_path, source="nse",
                fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
                now="2026-11-28T00:00:00+00:00")
        old_csv = (tmp_path / "company_names.csv").read_text(
            encoding="utf-8")

        def fail_fetch(url: str) -> str:
            raise NamesRefreshError("HTTPError 403 Forbidden")

        with pytest.raises(NamesRefreshError) as exc:
            refresh(tmp_path, source="nse", fetcher=fail_fetch,
                    now="2026-11-28T01:00:00+00:00")
        assert "fetch failed" in str(exc.value) or \
            "NSE fetch failed" in str(exc.value)
        assert (tmp_path / "company_names.csv").read_text(
            encoding="utf-8") == old_csv

    def test_html_instead_of_csv_typed_error(self, tmp_path):
        with pytest.raises(NamesRefreshError) as exc:
            refresh(tmp_path, source="nse",
                    fetcher=_fake_fetch_factory(
                        {"EQUITY_L": BSE_BLOCKED_HTML}),
                    now="2026-11-28T00:00:00+00:00")
        assert "NSE parse failed" in str(exc.value)

    def test_truncated_file_keeps_old(self, tmp_path):
        refresh(tmp_path, source="nse",
                fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
                now="2026-11-28T00:00:00+00:00")
        old_csv = (tmp_path / "company_names.csv").read_text(
            encoding="utf-8")
        with pytest.raises(NamesRefreshError) as exc:
            refresh(tmp_path, source="nse",
                    fetcher=_fake_fetch_factory(
                        {"EQUITY_L": NSE_TRUNCATED}),
                    now="2026-11-28T02:00:00+00:00")
        assert "sanity check failed" in str(exc.value)
        assert (tmp_path / "company_names.csv").read_text(
            encoding="utf-8") == old_csv

    def test_atomic_write_failure_typed_error(self, tmp_path):
        # make the store path a FILE so dir creation cannot succeed
        store = tmp_path / "store"
        store.write_text("not a dir", encoding="utf-8")
        with pytest.raises(NamesRefreshError):
            refresh(store, source="nse",
                    fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
                    now="2026-11-28T00:00:00+00:00")

    def test_dry_run_writes_nothing(self, tmp_path):
        report = refresh(
            tmp_path, source="nse", dry_run=True,
            fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
            now="2026-11-28T00:00:00+00:00")
        assert report["merged_total"] == 1200
        assert list(tmp_path.iterdir()) == [], (
            "dry-run must not write anything")


class TestStatus:
    def test_status_nothing_stored(self, tmp_path):
        st = status(tmp_path)
        assert st["stored"] is False
        assert "nd data names refresh" in st["hint"]

    def test_status_after_refresh(self, tmp_path):
        refresh(tmp_path, source="nse",
                fetcher=_fake_fetch_factory({"EQUITY_L": NSE_GOOD}),
                now="2026-11-28T00:00:00+00:00")
        st = status(tmp_path)
        assert st["stored"] is True
        assert st["meta"]["merged_total"] == 1200
        assert st["csv_rows"] == 1200
