"""P21-NAMES S2 (NAMES-API-1-2): fetch, sanity-check and store the
exchange name lists.

- Storage: NDR_NAMES_DIR (default per platform), files
  company_names.csv + names_meta.json, written ATOMICALLY (temp file
  + rename). Nothing is written inside the repo.
- Network: only the official hosts verified in the S0 probe; honest
  User-Agent; timeout 30 s; max 2 retries with backoff. No third-party
  mirrors.
- Failures raise NamesRefreshError and NEVER touch the stored file.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from niveshdristi.names.parse import (
    NamesParseError,
    merge,
    parse_bse,
    parse_nse,
)

NSE_URLS = (
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
)
BSE_URL = ("https://api.bseindia.com/BseIndiaAPI/api/"
           "ListofScripExchdate/w?listflag=Equity")

USER_AGENT = ("NiveshDristi-names-refresh/0.1 "
              "(educational research tool; one-shot explicit refresh; "
              "contact: local user)")
TIMEOUT_S = 30
MAX_RETRIES = 2
BACKOFF_S = 3.0

CSV_HEADER = "ticker,name,exchange,isin,source,retrieved_at,bse_code"


class NamesRefreshError(Exception):
    """Typed refresh failure ({error, hint} rendered by the CLI)."""


def names_dir() -> Path:
    """P21-NAMES R6: the stored-names directory.

    env NDR_NAMES_DIR wins; default %LOCALAPPDATA%\\NiveshDristi\\names
    (Windows) or ~/.local/share/niveshdristi/names elsewhere.
    """
    env = os.environ.get("NDR_NAMES_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "NiveshDristi" / "names"
    home = Path.home()
    return home / ".local" / "share" / "niveshdristi" / "names"


def fetch_url(url: str, fetcher=None) -> str:
    """GET with the honest UA, 30 s timeout, max 2 retries + backoff."""
    if fetcher is not None:
        return fetcher(url)
    last: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv, application/json, */*",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError,
                TimeoutError, OSError) as exc:
            last = exc
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_S * attempt)
    raise NamesRefreshError(
        f"fetch failed: {url} ({type(last).__name__}: {last})",
    ) from last


def _read_csv(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sanity(report: dict, previous_count: int | None) -> None:
    nse_count = report["sources"].get("NSE", {}).get("rows", 0)
    if nse_count < 1000:
        raise NamesRefreshError(
            f"sanity check failed: only {nse_count} NSE rows (< 1000) "
            "— the download is probably truncated or bot-blocked",
        )
    total = len(report["rows"])
    if previous_count is not None and not (
            previous_count * 0.5 <= total <= previous_count * 2.0):
        raise NamesRefreshError(
            f"sanity check failed: {total} merged rows vs previous "
            f"stored {previous_count} (outside 50%-200%)",
        )
    tickers = [r["ticker"] for r in report["rows"]]
    if len(tickers) != len(set(tickers)):
        raise NamesRefreshError(
            "sanity check failed: duplicate tickers after merge",
        )


def refresh(base_store: Path, source: str = "all", dry_run: bool = False,
            fetcher=None, now: str | None = None) -> dict:
    """Fetch -> parse -> merge -> sanity -> atomic write (unless dry-run).

    Returns the JSON report. On ANY failure the previously stored file
    is kept and NamesRefreshError is raised.
    """
    retrieved_at = now or datetime.now(UTC).isoformat(timespec="seconds")
    sources: dict[str, dict] = {}
    parsed: list[dict] = []

    if source in ("all", "nse"):
        text = None
        nse_err: Exception | None = None
        for url in NSE_URLS:
            try:
                text = fetch_url(url, fetcher)
                break
            except NamesRefreshError as exc:
                nse_err = exc
        if text is None:
            raise NamesRefreshError(
                f"NSE fetch failed on all hosts: {nse_err}",
            ) from nse_err
        try:
            rows = parse_nse(text)
        except NamesParseError as exc:
            raise NamesRefreshError(
                f"NSE parse failed: {exc} — content is not the expected "
                "CSV (bot-blocked HTML?)",
            ) from exc
        sources["NSE"] = {"url": NSE_URLS[0], "rows": len(rows),
                          "retrieved_at": retrieved_at}
        parsed.extend(rows)

    if source in ("all", "bse"):
        try:
            text = fetch_url(BSE_URL, fetcher)
            try:
                rows = parse_bse(text)
            except NamesParseError as exc:
                sources["BSE"] = {
                    "url": BSE_URL, "rows": 0, "retrieved_at": retrieved_at,
                    "error": f"BSE NOT AVAILABLE: {exc} (raw content was "
                             "not the expected CSV — bot-blocked)",
                }
            else:
                sources["BSE"] = {"url": BSE_URL, "rows": len(rows),
                                  "retrieved_at": retrieved_at}
                parsed.extend(rows)
        except NamesRefreshError as exc:
            sources["BSE"] = {"url": BSE_URL, "rows": 0,
                              "retrieved_at": retrieved_at,
                              "error": f"BSE NOT AVAILABLE: {exc}"}

    if not parsed:
        raise NamesRefreshError(
            "no rows parsed from any source; nothing stored",
        )

    merged = merge(parsed)
    meta_path = base_store / "names_meta.json"
    previous_count = None
    if meta_path.exists():
        try:
            meta = json.loads(_read_csv(meta_path))
            previous_count = int(meta.get("merged_total") or 0) or None
        except (json.JSONDecodeError, ValueError, OSError):
            previous_count = None

    report = {
        "rows": merged["rows"], "sources": sources,
        "conflicts": merged["conflicts"],
        "duplicates": merged["duplicates"],
        "merged_by_isin": merged["merged_by_isin"],
        "bse_only": merged["bse_only"],
        "merged_total": len(merged["rows"]),
        "retrieved_at": retrieved_at,
        "path": str(base_store / "company_names.csv"),
    }
    _sanity(report, previous_count)

    if dry_run:
        return report

    csv_text = CSV_HEADER + "\n" + "\n".join(
        _csv_row(r, retrieved_at) for r in merged["rows"]) + "\n"
    meta_out = {
        "sources": dict(sources),
        "row_counts": {k: v.get("rows", 0) for k, v in sources.items()},
        "merged_total": report["merged_total"],
        "conflicts": report["conflicts"],
        "duplicates": report["duplicates"],
        "sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "retrieved_at": retrieved_at,
    }
    try:
        base_store.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise NamesRefreshError(
            f"cannot create the names store dir {base_store}: {exc}",
        ) from exc
    _atomic_write(base_store / "company_names.csv", csv_text)
    _atomic_write(base_store / "names_meta.json",
                  json.dumps(meta_out, indent=1) + "\n")
    return report


def _csv_row(r: dict, retrieved_at: str) -> str:
    def esc(value: str) -> str:
        value = str(value)
        return f'"{value}"' if ('"' in value or "," in value) else value

    return ",".join([
        esc(r["ticker"]), esc(r["name"]), esc(r["exchange"]),
        esc(r.get("isin", "")), esc(r.get("source", "")),
        esc(retrieved_at), esc(r.get("bse_code", "")),
    ])


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise NamesRefreshError(
            f"atomic write failed for {path}: {exc}",
        ) from exc


def status(store: Path) -> dict:
    """Stored-names summary (the `nd data names status` payload)."""
    meta_path = store / "names_meta.json"
    csv_path = store / "company_names.csv"
    if not meta_path.exists() or not csv_path.exists():
        return {"stored": False, "path": str(store),
                "hint": "run nd data names refresh"}
    meta = json.loads(_read_csv(meta_path))
    rows = sum(max(1, line.count(",")) // 6
               for line in _read_csv(csv_path).splitlines()[1:]
               if line.strip())
    return {"stored": True, "path": str(store), "meta": meta,
            "csv_rows": rows}
