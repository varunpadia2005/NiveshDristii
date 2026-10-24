"""Session calendar (NEW, Phase 5) — neutral, no India literals.

The data-derived calendar is the UNION of dates present across all supplied
price frames. NO holiday dates are ever created here. Where an official
calendar (a plain set of session dates, supplied by the markets side) is
available for some years, CONFLICTS are reported (counts + lists) and never
silently resolved: the data calendar remains in use and the caller sets the
derived_calendar limitation flag.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date
from typing import Protocol

import polars as pl


class SessionClock(Protocol):
    """Neutral session-calendar interface injected into the engine."""

    def sessions(self) -> Iterator[date]:
        ...

    def next_session(self, after: date) -> date | None:
        ...

    def is_session(self, day: date) -> bool:
        ...

class DataCalendar:
    """Calendar derived from the dates present in price frames."""

    def __init__(self, dates: Iterable[date]) -> None:
        self._dates: list[date] = sorted(set(dates))

    @classmethod
    def from_frames(cls, frames: dict[str, pl.DataFrame]) -> DataCalendar:
        """Union of all dates present across the supplied frames."""
        all_dates: set[date] = set()
        for frame in frames.values():
            if "date" not in frame.columns:
                continue
            for raw in frame["date"].to_list():
                all_dates.add(date.fromisoformat(str(raw)[:10]))
        return cls(all_dates)

    def sessions(self) -> Iterator[date]:
        return iter(self._dates)

    def next_session(self, after: date) -> date | None:
        for day in self._dates:
            if day > after:
                return day
        return None

    def is_session(self, day: date) -> bool:
        return day in set(self._dates)


class CalendarConflicts:
    """Reported disagreements between the data calendar and an official one."""

    def __init__(
        self,
        data_on_non_session: list[date],
        official_session_without_data: list[date],
    ) -> None:
        self.data_on_non_session = sorted(data_on_non_session)
        self.official_session_without_data = sorted(official_session_without_data)

    @property
    def count(self) -> int:
        return len(self.data_on_non_session) + len(self.official_session_without_data)

    def summary(self) -> str:
        return (
            f"conflicts={self.count} "
            f"(data bars on official non-sessions: {len(self.data_on_non_session)}; "
            f"official sessions with no data bar: {len(self.official_session_without_data)})"
        )


def check_against_official(
    calendar: DataCalendar, official_sessions: set[date]
) -> CalendarConflicts:
    """Compare the data calendar with an official session set (plain dates).

    Neither source is altered; the caller keeps using the data calendar and
    sets the derived_calendar limitation flag.
    """
    data_set = set(calendar.sessions())
    data_on_non = data_set - official_sessions
    official_no_data = official_sessions - data_set
    return CalendarConflicts(sorted(data_on_non), sorted(official_no_data))
