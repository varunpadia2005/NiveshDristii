"""Local Parquet cache for market data (market-neutral).

- Deterministic cache keys: sha256 over (kind, market_id, symbol, range,
  as_of, extra params) — same query, same file.
- as_of-pinned queries are immutable historical facts: never considered
  stale. Only live queries (no as_of) honour `max_age`.
- Storage is Parquet files in a configurable directory (default `cache/`,
  gitignored). Tests must point this at tmp_path only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl


def cache_key(
    kind: str,
    market_id: str,
    symbol: str,
    start: date,
    end: date,
    *,
    as_of: date | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Deterministic cache key: same query always maps to the same file."""
    payload = "|".join(
        [
            kind,
            market_id,
            symbol,
            start.isoformat(),
            end.isoformat(),
            as_of.isoformat() if as_of else "",
            json.dumps(extra or {}, sort_keys=True),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ParquetCache:
    """File-per-key Parquet cache with staleness rules."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.parquet"

    def get(self, key: str, *, max_age: timedelta | None = None) -> pl.DataFrame | None:
        """Return the cached frame, or None on miss/stale entry."""
        path = self._path(key)
        if not path.exists():
            return None
        if max_age is not None:
            now = datetime.now(UTC)
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if now - mtime > max_age:
                return None
        return pl.read_parquet(path)

    def put(self, key: str, df: pl.DataFrame) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        df.write_parquet(self._path(key))

    def get_or_fetch(
        self,
        key: str,
        fetch: Callable[[], pl.DataFrame],
        *,
        max_age: timedelta | None = None,
    ) -> pl.DataFrame:
        """Cache-through read: fetch once, then serve from the cache."""
        hit = self.get(key, max_age=max_age)
        if hit is not None:
            return hit
        df = fetch()
        self.put(key, df)
        return df

    def prices(
        self,
        market_id: str,
        symbol: str,
        start: date,
        end: date,
        fetch: Callable[[], pl.DataFrame],
        *,
        as_of: date | None = None,
        live_max_age: timedelta | None = None,
    ) -> pl.DataFrame:
        """Cached prices read with PIT discipline.

        as_of-pinned queries are immutable (no staleness); live queries
        honour live_max_age.
        """
        key = cache_key("prices", market_id, symbol, start, end, as_of=as_of)
        max_age = None if as_of is not None else live_max_age
        return self.get_or_fetch(key, fetch, max_age=max_age)
