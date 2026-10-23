"""Data-quality checks producing a report object (market-neutral).

Checks: NaN OHLC rows, zero-volume bars, weekday gaps, stale last bar, and
suspected split/corporate-action discontinuities in RAW prices (a close
ratio far outside normal daily moves). Problems are REPORTED, never fixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import polars as pl

_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class QualityIssue:
    check: str
    detail: str
    severity: str  # "critical" | "warning"


@dataclass
class QualityReport:
    symbol: str
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    def count(self, check: str) -> int:
        return sum(1 for i in self.issues if i.check == check)

    def summary(self) -> str:
        parts = sorted({i.check for i in self.issues})
        return f"{self.symbol}: {len(self.issues)} issue(s) in {parts or 'no checks'}"


def check_prices(
    df: pl.DataFrame,
    symbol: str,
    *,
    reference_date: date | None = None,
    max_stale_days: int | None = None,
    jump_threshold: float = 0.40,
) -> QualityReport:
    """Run all quality checks on a normalized raw price frame."""
    report = QualityReport(symbol=symbol)

    missing_cols = [c for c in _REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        report.issues.append(
            QualityIssue("schema", f"missing columns: {missing_cols}", "critical")
        )
        return report

    # NaN OHLC rows (e.g. live latest-day placeholders)
    bad = df.filter(
        pl.col("open").is_null()
        | pl.col("high").is_null()
        | pl.col("low").is_null()
        | pl.col("close").is_null()
    )
    for d in bad["date"].to_list():
        report.issues.append(QualityIssue("nan_ohl", f"row {d}", "warning"))

    # Zero-volume bars
    zv = df.filter(pl.col("volume") == 0)
    for d in zv["date"].to_list():
        report.issues.append(QualityIssue("zero_volume", f"row {d}", "warning"))

    # Weekday gaps (Mon-Fri heuristic; market-neutral)
    if df.height >= 2:
        days = sorted({str(d)[:10] for d in df["date"].to_list()})
        d0 = date.fromisoformat(days[0])
        d1 = date.fromisoformat(days[-1])
        present = set(days)
        cur = d0
        while cur <= d1:
            if cur.weekday() < 5 and cur.isoformat() not in present:
                report.issues.append(QualityIssue("gap", f"missing weekday {cur}", "warning"))
            cur += timedelta(days=1)

    # Stale last bar (only when a reference date is given)
    if max_stale_days is not None and reference_date is not None and df.height:
        last = date.fromisoformat(str(df["date"].max())[:10])
        if (reference_date - last).days > max_stale_days:
            detail = f"last bar {last} vs reference {reference_date}"
            report.issues.append(QualityIssue("stale_bars", detail, "warning"))

    # Suspected split/corporate-action discontinuity in RAW prices
    if df.height >= 2 and jump_threshold:
        sorted_df = df.sort("date").filter(pl.col("close").is_not_null())
        closes = sorted_df["close"].to_list()
        dates = [str(x)[:10] for x in sorted_df["date"].to_list()]
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev and prev != 0:
                change = abs(closes[i] / prev - 1.0)
                if change > jump_threshold:
                    report.issues.append(
                        QualityIssue(
                            "split_discontinuity",
                            f"{dates[i]}: close ratio {closes[i] / prev:.3f} "
                            f"({change:.0%} move on raw prices)",
                            "critical",
                        )
                    )
    return report
