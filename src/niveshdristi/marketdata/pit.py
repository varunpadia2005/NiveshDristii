"""Point-in-time store for fundamentals (CHANGES.md C4, market-neutral).

Every record carries period_end, announced_at and source. Queries take an
as_of date and return ONLY rows with announced_at <= as_of — a result
announced tomorrow must be invisible today.

When only period_end is known, a conservative lag can be applied via
`put_with_lag` (announced_at = period_end + lag_days, approximate=True).
The lag is OFF by default and always flags records as approximate PIT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class PITRecord:
    symbol: str
    metric: str
    value: float
    period_end: date
    announced_at: date
    source: str
    approximate: bool = False


@dataclass
class PITStore:
    """In-memory point-in-time store (persistence arrives with the data layer)."""

    _records: list[PITRecord] = field(default_factory=list)

    def put(self, record: PITRecord) -> None:
        self._records.append(record)

    def put_with_lag(self, record: PITRecord, lag_days: int) -> None:
        """Conservative availability lag: approximate PIT, always flagged."""
        lagged = PITRecord(
            symbol=record.symbol,
            metric=record.metric,
            value=record.value,
            period_end=record.period_end,
            announced_at=record.period_end + _days(lag_days),
            source=record.source,
            approximate=True,
        )
        self._records.append(lagged)

    def query(
        self,
        symbol: str,
        as_of: date,
        *,
        metric: str | None = None,
    ) -> list[PITRecord]:
        """Records for `symbol` public by `as_of` (announced_at <= as_of only)."""
        return sorted(
            [
                r
                for r in self._records
                if r.symbol == symbol
                and r.announced_at <= as_of
                and (metric is None or r.metric == metric)
            ],
            key=lambda r: (r.metric, r.period_end),
        )

    def latest(self, symbol: str, metric: str, as_of: date) -> PITRecord | None:
        """Most recent public-by-as_of record for one metric, or None."""
        rows = self.query(symbol, as_of, metric=metric)
        return rows[-1] if rows else None


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)
