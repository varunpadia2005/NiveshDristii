"""P21-NAMES S1: parser + merge tests (synthetic-labelled fixtures, no
network). Mutation target: breaking the ISIN merge must FAIL
test_isin_merge_wins_nse_ticker."""

from __future__ import annotations

import pytest

from niveshdristi.names.parse import (
    NamesParseError,
    merge,
    parse_bse,
    parse_nse,
)

NSE_HEADER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, "
    "MARKET LOT, ISIN NUMBER, FACE VALUE")

NSE_ROWS = (
    "RELIANCE,Reliance Industries Limited,EQ,06-DEC-1995,10,1,"
    "INE002A01018,10\n"
    "TCS,Tata Consultancy Services Limited,EQ,25-AUG-2004,1,1,"
    "INE467B01029,1\n"
    "INFOLTD,Some Debt Note Limited,GS,01-JAN-2020,10,1,"
    "INE999D01017,10\n"
    ",,,\n"
    "PARTIAL,Only Symbol Here,EQ,01-JAN-2020,10,1,INE123E01012,1\n")

NSE_CSV = NSE_HEADER + "\n" + NSE_ROWS

BSE_CSV = (
    "ScripCode,ScripId,ScripName,ISIN,Status\n"
    "500325,RELIANCE,Reliance Industries Ltd,INE002A01018,Active\n"
    "532540,TCS,Tata Consultancy Services Ltd,INE467B01029,Active\n"
    "500001,SOMEBSE,Some BSE Only Company,,Active\n"
    "500003,OTHERBSE,Another BSE Company,,Active\n"
    "500002,INACTIVECO,Delisted But Listed Row,INE777E01011,Suspended\n")


class TestParseNse:
    def test_parses_equity_rows_and_skips_non_equity(self):
        rows = parse_nse(NSE_CSV)
        tickers = {r["ticker"] for r in rows}
        assert tickers == {"RELIANCE", "TCS", "PARTIAL"}
        rel = next(r for r in rows if r["ticker"] == "RELIANCE")
        assert rel["name"] == "Reliance Industries Limited"
        assert rel["exchange"] == "NSE"
        assert rel["isin"] == "INE002A01018"

    def test_missing_columns_typed_error(self):
        with pytest.raises(NamesParseError) as exc:
            parse_nse("FOO,BAR\n1,2\n")
        assert "missing columns" in str(exc.value)

    def test_malformed_row_typed_error(self):
        bad = NSE_CSV.replace(
            "PARTIAL,Only Symbol Here,EQ,01-JAN-2020,10,1,INE123E01012,1",
            "PARTIAL,,EQ,01-JAN-2020,10,1,INE123E01012,1")
        with pytest.raises(NamesParseError) as exc:
            parse_nse(bad)
        assert "row 6" in str(exc.value)

    def test_bom_and_empty_file(self):
        rows = parse_nse("﻿" + NSE_CSV)
        assert rows
        with pytest.raises(NamesParseError):
            parse_nse("")


class TestParseBse:
    def test_parses_active_rows_skips_inactive(self):
        rows = parse_bse(BSE_CSV)
        tickers = {r["ticker"] for r in rows}
        assert tickers == {"RELIANCE", "TCS", "SOMEBSE", "OTHERBSE"}
        assert all(r["exchange"] == "BSE" for r in rows)

    def test_quotes_commas_and_non_ascii_names(self):
        csv_text = (
            "ScripCode,ScripId,ScripName,ISIN,Status\n"
            '500001,M&M,"Mahindra & Mahindra, Ltd",INE101A01026,Active\n'
            "500002,UNICODE,Élite Ünïcode Limited,INE102A01026,Active\n")
        rows = parse_bse(csv_text)
        names = {r["name"] for r in rows}
        assert "Mahindra & Mahindra, Ltd" in names
        assert "Élite Ünïcode Limited" in names


class TestMerge:
    def test_isin_merge_wins_nse_ticker(self):
        merged = merge(parse_nse(NSE_CSV) + parse_bse(BSE_CSV))
        rows = {r["ticker"]: r for r in merged["rows"]}
        # merged by ISIN: one RELIANCE row, NSE ticker, bse_code kept
        assert rows["RELIANCE"]["name"] == "Reliance Industries Limited"
        assert rows["RELIANCE"].get("bse_code") == "500325"
        assert merged["merged_by_isin"] >= 2
        # BSE-only row keeps its own ticker
        assert "SOMEBSE" in rows
        assert merged["bse_only"] >= 1

    def test_conflicts_reported_not_silently_resolved(self):
        nse = parse_nse(NSE_CSV)
        bse_text = BSE_CSV.replace(
            "Reliance Industries Ltd", "Conflicting Name Ltd")
        merged = merge(nse + parse_bse(bse_text))
        assert merged["conflicts"], "name conflict must be reported"
        assert merged["conflicts"][0]["isin"] == "INE002A01018"

    def test_duplicate_ticker_reported(self):
        dup = NSE_CSV + (
            "RELIANCE,Reliance Duplicate Row,EQ,01-JAN-2020,10,1,"
            "INE002A01018,10\n")
        merged = merge(parse_nse(dup))
        assert merged["duplicates"], "duplicate must be reported"

    def test_non_vacuity(self):
        merged = merge(parse_nse(NSE_CSV) + parse_bse(BSE_CSV))
        assert len(merged["rows"]) >= 5
