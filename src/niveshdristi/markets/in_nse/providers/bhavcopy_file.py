"""NSE bhavcopy FILE parser for IN_NSE (sec_bhavdata_full CSV format).

FILE-BASED ONLY: the user downloads sec_bhavdata_full_DDMMYYYY.csv files
manually in a browser from the NSE archives into a configured directory.
There is deliberately NO automated downloader — NSE's terms of use prohibit
systematic automated data collection (see docs/VERIFY.md section 9).

Parses the official column schema, fails loudly on any mismatch, and types
DELIV_QTY (int) and DELIV_PER (float) — the delivery data that enriches
prices with India-specific liquidity information.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import polars as pl

from niveshdristi.core.errors import ProviderError

# Official sec_bhavdata_full header (verified against the real file,
# D:/Nivesh Dristi/p2_probe/bhavcopy_20261023.csv, 2026-10-23)
EXPECTED_COLUMNS = [
    "SYMBOL", "SERIES", "DATE1", "PREV_CLOSE", "OPEN_PRICE", "HIGH_PRICE",
    "LOW_PRICE", "LAST_PRICE", "CLOSE_PRICE", "AVG_PRICE", "TTL_TRD_QNTY",
    "TURNOVER_LACS", "NO_OF_TRADES", "DELIV_QTY", "DELIV_PER",
]

_COLUMN_DTYPES = {
    "PREV_CLOSE": pl.Float64,
    "OPEN_PRICE": pl.Float64,
    "HIGH_PRICE": pl.Float64,
    "LOW_PRICE": pl.Float64,
    "LAST_PRICE": pl.Float64,
    "CLOSE_PRICE": pl.Float64,
    "AVG_PRICE": pl.Float64,
    "TTL_TRD_QNTY": pl.Int64,
    "TURNOVER_LACS": pl.Float64,
    "NO_OF_TRADES": pl.Int64,
    "DELIV_QTY": pl.Int64,
    "DELIV_PER": pl.Float64,
}


def parse_bhavcopy_csv(path: str | Path) -> pl.DataFrame:
    """Parse one sec_bhavdata_full CSV into a typed, date-keyed frame.

    Raises ProviderError on schema mismatch (wrong/missing/reordered
    columns). Lines starting with '#' are skipped (synthetic-fixture labels;
    real NSE files have none).
    """
    path = Path(path)
    text_lines = [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    header = [c.strip() for c in text_lines[0].split(",")]
    if header != EXPECTED_COLUMNS:
        missing = [c for c in EXPECTED_COLUMNS if c not in header]
        extra = [c for c in header if c not in EXPECTED_COLUMNS]
        raise ProviderError(
            f"bhavcopy schema mismatch in {path.name}: "
            f"missing={missing or 'none'} extra={extra or 'none'}"
        )

    df = pl.read_csv("\n".join(text_lines).encode("utf-8"))
    # Real NSE files have a space after each comma: " SERIES", " 100.00", ...
    df = df.rename({c: c.strip() for c in df.columns})
    str_cols = [c for c in df.columns if df.schema[c] == pl.String]
    if str_cols:
        # Strip the padding spaces real files carry, and map the official
        # "-" placeholder (no delivery data for some series) to null.
        df = df.with_columns(
            [
                pl.when(pl.col(c).str.strip_chars() == "-")
                .then(None)
                .otherwise(pl.col(c).str.strip_chars())
                .alias(c)
                for c in str_cols
            ]
        )
    df = df.with_columns(pl.col("DATE1").str.to_date("%d-%b-%Y"))
    for col, dtype in _COLUMN_DTYPES.items():
        df = df.with_columns(pl.col(col).cast(dtype, strict=True))
    return df.sort("DATE1", "SYMBOL")


class BhavcopyFileStore:
    """Delivery-data enrichment source over manually downloaded files.

    NO network access of any kind: reads only files already present in
    `directory` (user downloads them in a browser).
    """

    provider_name = "bhavcopy_files"

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def available_dates(self) -> list[date]:
        """Trading dates with a downloaded file, parsed from filenames."""
        out = []
        for f in sorted(self.directory.glob("sec_bhavdata_full_*.csv")):
            try:
                out.append(datetime.strptime(f.stem.split("_")[-1], "%d%m%Y").date())
            except ValueError:
                continue
        return out

    def load_day(self, day: date) -> pl.DataFrame:
        """Load one day's file; ProviderError if the file is absent."""
        fname = self.directory / f"sec_bhavdata_full_{day.strftime('%d%m%Y')}.csv"
        if not fname.exists():
            raise ProviderError(
                f"bhavcopy file for {day.isoformat()} not found in {self.directory} "
                "(download it manually in a browser; there is no automated downloader)"
            )
        return parse_bhavcopy_csv(fname)

    def delivery_for(self, symbol: str, day: date, series: str = "EQ") -> pl.DataFrame:
        """Delivery quantity/percent for one symbol on one day."""
        df = self.load_day(day)
        return df.filter((pl.col("SYMBOL") == symbol) & (pl.col("SERIES") == series)).select(
            ["SYMBOL", "SERIES", "DATE1", "TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER"]
        )
