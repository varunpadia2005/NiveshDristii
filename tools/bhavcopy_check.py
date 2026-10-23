#!/usr/bin/env python
"""Opt-in checker for a REAL downloaded bhavcopy file — NOT part of pytest.

Usage: python tools/bhavcopy_check.py <path to sec_bhavdata_full_*.csv>
(or set ND_BHAVCOPY_FILE). Runs the production parser against a real file
you downloaded manually, so schema/format changes are caught early.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from niveshdristi.markets.in_nse.providers.bhavcopy_file import parse_bhavcopy_csv  # noqa: E402


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        import os

        target = os.environ.get("ND_BHAVCOPY_FILE")
    if not target:
        print("usage: python tools/bhavcopy_check.py <sec_bhavdata_full_*.csv>")
        return 2
    df = parse_bhavcopy_csv(target)
    print("parsed OK:", df.shape, "| dates:", df["DATE1"].unique().to_list())
    print("dtypes:", dict(df.schema))
    eq = df.filter(df["SERIES"] == "EQ")
    print("EQ rows:", eq.height, "| DELIV_PER mean:", round(eq["DELIV_PER"].mean(), 2))
    print(eq.select(["SYMBOL", "DATE1", "TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER"]).head(3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
