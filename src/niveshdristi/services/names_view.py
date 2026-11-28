"""P21-NAMES S3 (NAMES-API-1-4): the single symbol -> display-name
resolver. Lives in services so both UIs share it (the services import
boundary only allows core/paper/markets/engine/alpha/marketdata/
services imports).

Reads (cached by file mtime, reloaded on change):
1. the stored refresh file  (NDR_NAMES_DIR / platform default)
2. the owner's fallback CSV (NDR_NAMES_FALLBACK or
   D:/NiveshDristi/inputs/company_names.csv) if present;
3. otherwise nothing: the caller falls back to the ticker itself.

No invented data: a name is ever only a value read from one of those
files. Search ranks: exact ticker > name prefix > name substring
(case-insensitive), limit capped at 50.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

_FALLBACK = Path("D:/NiveshDristi/inputs/company_names.csv")
_MAX_LIMIT = 50

_cache: dict[str, tuple[float, dict[str, dict]]] = {}


def _read_csv_rows(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            ticker = (raw.get("ticker") or "").strip().upper()
            name = (raw.get("name") or "").strip()
            if not ticker or not name:
                continue
            out[ticker] = {
                "name": name,
                "exchange": (raw.get("exchange") or "").strip(),
            }
    return out


def names_dir() -> Path:
    """The stored-names directory (R6): env NDR_NAMES_DIR wins; default
    is the platform data dir (Windows: LOCALAPPDATA / NiveshDristi /
    names, else ~/.local/share/niveshdristi/names)."""
    env = os.environ.get("NDR_NAMES_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "NiveshDristi" / "names"
    return Path.home() / ".local" / "share" / "niveshdristi" / "names"


def load_names() -> dict[str, dict]:
    """ticker -> {name, exchange}; cached per source file by mtime."""
    sources: list[tuple[str, Path]] = []
    store = names_dir() / "company_names.csv"
    if store.exists():
        sources.append(("refresh", store))
    fallback = Path(os.environ.get("NDR_NAMES_FALLBACK", str(_FALLBACK)))
    if fallback.exists():
        sources.append(("fallback", fallback))

    out: dict[str, dict] = {}
    for label, path in sources:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        cached = _cache.get(str(path))
        if cached and cached[0] == mtime:
            rows = cached[1]
        else:
            rows = _read_csv_rows(path)
            _cache[str(path)] = (mtime, rows)
        for ticker, row in rows.items():
            if ticker not in out:
                out[ticker] = {"name": row["name"],
                               "exchange": row.get("exchange", ""),
                               "source": label}
    return out


def resolve(symbol: str) -> dict | None:
    """{name, exchange, source} for a ticker, or None (caller falls
    back to the ticker itself)."""
    return load_names().get((symbol or "").strip().upper())


def search(q: str, limit: int = 20) -> list[dict]:
    """Ranked search: exact ticker > name prefix > name substring."""
    query = (q or "").strip().upper()
    if len(query) < 1:
        return []
    limit = max(1, min(int(limit), _MAX_LIMIT))
    ranked: list[tuple[int, str, dict]] = []
    for ticker, row in load_names().items():
        name = row["name"].upper()
        if ticker == query:
            rank = 0
        elif ticker.startswith(query) or name.startswith(query):
            rank = 1
        elif query in ticker or query in name:
            rank = 2
        else:
            continue
        ranked.append((rank, ticker, row))
    ranked.sort(key=lambda x: (x[0], x[1]))
    return [{"ticker": t, "name": r["name"],
             "exchange": r.get("exchange", ""),
             "source": r.get("source", "")}
            for _, t, r in ranked[:limit]]
