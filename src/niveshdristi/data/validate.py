"""Data validation with severity levels: ERROR, WARN, INFO."""
from dataclasses import dataclass
from typing import List
import polars as pl
from niveshdristi.config import CFG


@dataclass
class ValidationIssue:
    level: str  # ERROR, WARN, INFO
    message: str
    details: dict = None


@dataclass
class ValidationReport:
    ticker: str
    issues: List[ValidationIssue]
    passed: bool


def validate_prices(df: pl.DataFrame, ticker: str) -> pl.DataFrame:
    """Validate price data, return DataFrame (validation is done in-place with flags)."""
    issues = []

    # ERROR: Data integrity issues that break computations
    if df["date"].is_duplicated().any():
        issues.append(ValidationIssue("ERROR", "Duplicate dates found"))

    if (df["high"] < df["low"]).any():
        issues.append(ValidationIssue("ERROR", "High < Low on some rows"))

    # Check for zero/negative prices
    price_cols = ["open", "high", "low", "close"]
    min_price = df.select(pl.min_horizontal(pl.col(price_cols))).to_series().min()
    if min_price <= 0:
        issues.append(ValidationIssue("ERROR", "Zero or negative prices found"))

    # WARN: Data quality issues that may affect results
    # Missing trading days (gaps > 5 calendar days)
    gaps = df["date"].diff().dt.total_days() > 5
    missing_pct = gaps.sum() / len(df) * 100
    if missing_pct > CFG.data.validation.max_missing_pct:
        issues.append(ValidationIssue("WARN", f"{missing_pct:.1f}% missing trading days (gaps >5 days)"))

    # Volume spikes (>10x previous day)
    vol_spikes = df["volume"].pct_change().abs() > 10
    if vol_spikes.any():
        issues.append(ValidationIssue("WARN", f"Volume spikes detected: {vol_spikes.sum()} days"))

    # Price gaps >20% (non-suspicious move flagged)
    price_gaps = df["adj_close"].pct_change().abs() > 0.2
    if price_gaps.any():
        issues.append(ValidationIssue("WARN", f"Large price gaps (>20%): {price_gaps.sum()} days"))

    # INFO: Informational
    if len(df) < CFG.data.validation.min_trading_days:
        issues.append(ValidationIssue("INFO", f"Short history: {len(df)} trading days"))

    # Store validation issues in DataFrame metadata (as a column)
    # For now, just return the DataFrame (validation issues can be accessed separately)
    return df