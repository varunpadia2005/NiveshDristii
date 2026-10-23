#!/usr/bin/env python
"""Live yfinance smoke probe — OPT-IN, never run by pytest or the gate.

Usage: python tools/probe_yfinance.py [SYMBOL]
Makes 2 live requests (raw + adjusted) for one symbol. yfinance is
unofficial; personal/educational use only.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))

from niveshdristi.markets.in_nse.providers.yfinance_adapter import YFinanceClient  # noqa: E402


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    end = date.today()
    start = end - timedelta(days=10)
    client = YFinanceClient()
    ps = client.prices(symbol, start, end)
    print("symbol:", symbol, "| rows:", ps.raw.height, "| provider:", client.provider_name)
    print("columns:", ps.raw.columns)
    print("latest raw date:", ps.raw["date"].max() if ps.raw.height else None)
    print("nan_ohl flags:", ps.flags or "none")
    print(ps.raw.tail(3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
