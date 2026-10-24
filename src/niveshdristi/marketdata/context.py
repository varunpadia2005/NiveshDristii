"""As-of-limited ModelInputs builder — the ONLY way data reaches models.

build_model_inputs validates at construction that no price row is dated
after as_of (typed DataError otherwise). build_from_full_frames first
truncates every frame to as_of (what a live data handle would deliver) and
then builds, so the no-look-ahead invariant holds by construction.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

import polars as pl

from niveshdristi.core.alpha import ModelInputs
from niveshdristi.core.errors import DataError


def _as_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def _row_dates(df: pl.DataFrame) -> list[str]:
    """ISO date strings of the 'date' column (accepts str or Date dtype)."""
    if "date" not in df.columns:
        raise DataError("price frame has no 'date' column")
    return [str(d)[:10] for d in df["date"].to_list()]


def truncate_to_as_of(df: pl.DataFrame, as_of: date) -> pl.DataFrame:
    """Keep only rows dated on or before as_of."""
    cutoff = as_of.isoformat()
    return df.filter(pl.col("date").cast(pl.String).str.slice(0, 10) <= cutoff)


def _validate_no_future_rows(frames: Mapping[str, Any], as_of_d: date, kind: str) -> None:
    """Raise DataError if any dateable frame in `frames` has rows past as_of."""
    cutoff = as_of_d.isoformat()
    for name, value in frames.items():
        if not isinstance(value, pl.DataFrame) or "date" not in value.columns:
            continue
        future = [d for d in _row_dates(value) if d > cutoff]
        if future:
            raise DataError(
                f"{kind} frame for {name!r} contains rows dated after as_of "
                f"{cutoff}: {sorted(set(future))[:5]}"
            )


def build_model_inputs(
    *,
    as_of: datetime | date,
    prices: Mapping[str, pl.DataFrame],
    fundamentals: Mapping[str, tuple] | None = None,
    aux: Mapping[str, Any] | None = None,
) -> ModelInputs:
    """Validate frames against as_of and build a read-only ModelInputs.

    Raises DataError naming the symbol/role and offending dates if any price
    or aux frame has rows dated after as_of — the point-in-time invariant is
    enforced HERE (aux frames with a date column are validated by ROLE).
    """
    as_of_d = _as_date(as_of)
    _validate_no_future_rows(prices, as_of_d, kind="price")
    _validate_no_future_rows(aux or {}, as_of_d, kind="aux")
    return ModelInputs(
        as_of=as_of_d,
        prices=MappingProxyType(dict(prices)),
        fundamentals=MappingProxyType(dict(fundamentals or {})),
        aux=MappingProxyType(dict(aux or {})),
    )


def build_from_full_frames(
    *,
    as_of: datetime | date,
    prices: Mapping[str, pl.DataFrame],
    fundamentals: Mapping[str, tuple] | None = None,
    aux: Mapping[str, Any] | None = None,
) -> ModelInputs:
    """Truncate every frame to as_of (the as_of-limited data handle), then build.

    Price frames AND dateable aux frames are truncated to as_of.
    """
    as_of_d = _as_date(as_of)
    truncated = {sym: truncate_to_as_of(df, as_of_d) for sym, df in prices.items()}
    aux_truncated = {
        role: (truncate_to_as_of(v, as_of_d) if isinstance(v, pl.DataFrame) else v)
        for role, v in (aux or {}).items()
    }
    return build_model_inputs(
        as_of=as_of_d, prices=truncated, fundamentals=fundamentals, aux=aux_truncated
    )
