"""P21-NAMES S1 (NAMES-API-1-1): parse + merge exchange name lists.

Pure functions only — no network, no filesystem. Inputs are the raw CSV
text from the exchange (or synthetic fixtures in tests); output is the
common row schema:

    {"ticker", "name", "exchange", "isin", "series"}

Rules (documented, tested):
- NSE: keep equity series only — SERIES in {"EQ", "BE", "BZ"} (EQ =
  main board equity, BE = trade-for-trade equity, BZ = essentially
  suspended-but-listed equity). Everything else (SM/ST/GS/SG/W3/...)
  is debt/derivative/preference and is dropped.
- BSE rows are parsed from the documented column layout when BSE
  becomes reachable; BSE-only rows use the BSE scrip id as ticker.
- Merge by ISIN: the same company listed on both exchanges becomes one
  row (NSE symbol wins as ticker, the bse_code is kept). BSE-only rows
  keep their own ticker.
- Whitespace is normalised; duplicates and conflicts are REPORTED in
  the result, never silently dropped.
"""

from __future__ import annotations

import csv
import io

EQUITY_SERIES = frozenset({"EQ", "BE", "BZ"})


class NamesParseError(ValueError):
    """Typed parse failure (malformed CSV, missing columns, BOM/empty)."""


def _clean(value: str) -> str:
    return " ".join(value.split())


def parse_nse(text: str) -> list[dict]:
    """Parse the NSE equity master CSV (EQUITY_L.csv).

    Required columns: SYMBOL, NAME OF COMPANY, SERIES, ISIN NUMBER.
    Rows whose SERIES is not equity are counted and skipped (kept in
    the report as skipped_series).
    """
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in (next(reader, []) or [])]
    required = {"SYMBOL", "NAME OF COMPANY", "SERIES", "ISIN NUMBER"}
    missing = required - set(header)
    if missing:
        raise NamesParseError(
            f"NSE csv missing columns: {sorted(missing)} "
            f"(found {header[:8]})")
    idx = {h: header.index(h) for h in required}

    def cell(raw: list[str], column: str) -> str:
        i = idx[column]
        return raw[i] if i < len(raw) else ""

    rows: list[dict] = []
    for i, raw in enumerate(reader, start=2):
        symbol = _clean(cell(raw, "SYMBOL"))
        name = _clean(cell(raw, "NAME OF COMPANY"))
        series = cell(raw, "SERIES").strip().upper()
        isin = _clean(cell(raw, "ISIN NUMBER"))
        if not symbol and not name:
            continue  # fully empty line
        if not symbol or not name:
            raise NamesParseError(
                f"NSE row {i}: missing SYMBOL or NAME OF COMPANY")
        if series not in EQUITY_SERIES:
            continue
        rows.append({"ticker": symbol.upper(), "name": name,
                     "exchange": "NSE", "isin": isin, "series": series})
    return rows


def parse_bse(text: str) -> list[dict]:
    """Parse the BSE active equity scrip list (when reachable).

    Documented layout (ListofScripExchdate Equity JSON/CSV): ScripCode,
    ScripId (ticker), ScripName, ISIN, Status. Rows whose Status is not
    "Active" are skipped.
    """
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    required = {"ScripCode", "ScripId", "ScripName", "ISIN"}
    missing = required - {h.strip() for h in header}
    if missing:
        raise NamesParseError(
            f"BSE csv missing columns: {sorted(missing)} (found "
            f"{header[:8]})")
    rows: list[dict] = []
    for i, raw in enumerate(reader, start=2):
        scrip_id = _clean(raw.get("ScripId") or "")
        name = _clean(raw.get("ScripName") or "")
        code = _clean(raw.get("ScripCode") or "")
        isin = _clean(raw.get("ISIN") or "")
        status = (raw.get("Status") or "").strip().title()
        if not scrip_id and not name:
            continue
        if not scrip_id or not name:
            raise NamesParseError(
                f"BSE row {i}: missing ScripId or ScripName")
        if status and status != "Active":
            continue
        rows.append({"ticker": scrip_id.upper(), "name": name,
                     "exchange": "BSE", "isin": isin,
                     "series": "EQ", "bse_code": code})
    return rows


def merge(rows: list[dict]) -> dict:
    """Merge parsed rows into the common schema, by ISIN where possible.

    Returns {"rows": [...], "conflicts": [...], "duplicates": [...],
             "bse_only": count, "merged_by_isin": count}. Conflicts
    (same ISIN, different company name) are REPORTED, never silently
    resolved; per-ticker duplicates within one exchange are reported
    and deduplicated by (exchange, ticker).
    """
    by_key: dict[str, dict] = {}
    conflicts: list[dict] = []
    duplicates: list[dict] = []
    merged_by_isin = 0
    bse_only = 0
    seen: set[tuple[str, str]] = set()

    # NSE first (wins as ticker on ISIN merge), then BSE.
    ordered = sorted(rows, key=lambda r: 0 if r["exchange"] == "NSE"
                     else 1)
    for r in ordered:
        key = r["isin"] if r.get("isin") else (
            f"{r['exchange']}:{r['ticker']}")
        existing = by_key.get(key)
        if existing is not None and r["exchange"] != existing["exchange"]:
            # same ISIN on both exchanges -> one row, NSE symbol wins
            if existing["name"].casefold() != r["name"].casefold():
                conflicts.append({"isin": r.get("isin", ""),
                                  "nse_name": existing["name"],
                                  "bse_name": r["name"]})
            if r["exchange"] == "BSE":
                existing["bse_code"] = r.get("bse_code", "")
                merged_by_isin += 1
            continue
        tk = (r["exchange"], r["ticker"])
        if tk in seen:
            duplicates.append({"exchange": r["exchange"],
                               "ticker": r["ticker"],
                               "name": r["name"]})
            continue
        seen.add(tk)
        if r["exchange"] == "BSE" and not r.get("isin"):
            bse_only += 1
        by_key[key] = dict(r)

    out_rows = []
    for r in by_key.values():
        row = {"ticker": r["ticker"], "name": r["name"],
               "exchange": r["exchange"], "isin": r.get("isin", ""),
               "source": r["exchange"]}
        if r.get("bse_code"):
            row["bse_code"] = r["bse_code"]
        out_rows.append(row)
    out_rows.sort(key=lambda r: r["ticker"])
    return {"rows": out_rows, "conflicts": conflicts,
            "duplicates": duplicates, "merged_by_isin": merged_by_isin,
            "bse_only": bse_only}
