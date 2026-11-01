"""SYNTHETIC demo paper fund generator (NEW, D1c).

stdlib + project modules only; NO network, NO real instruments (SYN-named),
NEVER the repo and NEVER the default fund directory (a caller-supplied base
is required; the documented default lives OUTSIDE the repo). Writes a
header-labelled SYNTHETIC DEMO fund with 130+ sessions, real
TimeSeriesMomentum, fills, decision sidecars and full banners.

Usage:
    python tools/make_demo_fund.py --base "D:/Nivesh Dristi/demo_funds"
    python tools/make_demo_fund.py --base ... --tamper-ledger  (creates <id>_tampered COPY)
    python tools/make_demo_fund.py --base ... --tamper-sidecar (creates <id>_tampered COPY)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum  # noqa: E402
from niveshdristi.core.limitations import DataLimitations  # noqa: E402
from niveshdristi.core.market_rules import MarketRules  # noqa: E402
from niveshdristi.engine.advance import ModelBundle, RebalanceSchedule  # noqa: E402
from niveshdristi.paper.fund import create_fund, tick  # noqa: E402
from niveshdristi.portfolio.risk_gates import GateLimits  # noqa: E402

DEMO_BASE_DEFAULT = Path(r"D:\Nivesh Dristi\demo_funds")  # OUTSIDE the repo
SESSIONS = 132
N_TICKS = 130


def _demo_frames(n=SESSIONS):
    end = date(2026, 10, 30)
    dates = [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]
    c = [round(100.0 * (1.0025 ** i), 6) for i in range(n)]
    common = {
        "date": dates, "close": c,
        "high": [v * 1.01 for v in c], "low": [v * 0.99 for v in c],
        "adj_close": c, "adj_high": [v * 1.01 for v in c],
        "adj_low": [v * 0.99 for v in c], "volume": [1_000_000] * n,
    }
    return {"SYN090": {"frame": common}, "SYN091": {"frame": common}}


def _synthetic_frames():
    import polars as pl

    raw = _demo_frames()
    out = {}
    for symbol, spec in raw.items():
        common = dict(spec["frame"])
        common["close"] = [
            v * (1.0 if symbol == "SYN090" else 0.5) for v in common["close"]
        ]
        # (scale other columns for SYN091 by the same factor via close ratio)
        out[symbol] = pl.DataFrame(common)
    return out


def build_demo_fund(base: Path, fund_id: str = "demo_synthetic") -> Path:
    frames = _synthetic_frames()
    dates = sorted(frames["SYN090"]["date"].to_list())
    created = date.fromisoformat(dates[0]) - timedelta(days=1)
    limitations = DataLimitations(CODES=frozenset({
        "rates_unverified", "approximate_universe", "survivorship_universe",
        "stub_models_used", "benchmark_not_tri", "regime_vol_proxy",
    }))
    create_fund(
        f"{fund_id}", base=base, created=created, config_digest="synthetic-demo",
        rules=MarketRules(market_id="TEST_M"),
        limitations=limitations, rates_verified=False,
        initial_cash=1_000_000.0, universe=["SYN090", "SYN091"],
    )
    # label the header SYNTHETIC DEMO (extra header line, outside the hash
    # chain of records — the fund_header line is updated in place)

    ledger_path = base / fund_id / "ledger.jsonl"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["note"] = "SYNTHETIC DEMO - not real instruments, not real data"
    lines[0] = json.dumps(header, sort_keys=True, separators=(",", ":"))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bundle = ModelBundle([TimeSeriesMomentum()])
    for d in dates[:N_TICKS]:
        tick(
            fund_id, base=base,
            fetch_bars=lambda u, day: frames,  # noqa: B023 - loop var unused
            clock_now=date.fromisoformat(d), models=bundle,
            rules=MarketRules(market_id="TEST_M"),
            limits=GateLimits(max_position_pct=1.0, min_cash_pct=0.0,
                              turnover_max=1.0),
            rebalance=RebalanceSchedule(), universe=["SYN090", "SYN091"],
        )
    return base / fund_id


def tampered_copy(base: Path, fund_id: str, mode: str) -> Path:
    """Copy <fund_id> to <fund_id>_tampered_<mode> and corrupt it."""
    src = base / fund_id
    dst = base / f"{fund_id}_tampered_{mode}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    if mode == "ledger":
        target = dst / "ledger.jsonl"
        lines = target.read_text(encoding="utf-8").splitlines()
        # corrupt the FIRST RECORD line's cash with a DIGIT FLIP (JSON stays
        # valid; the stored hash breaks). The header (index 0) is skipped.
        for i in range(1, len(lines)):
            if '"cash_after":1000000.0' in lines[i]:
                lines[i] = lines[i].replace(
                    '"cash_after":1000000.0', '"cash_after":1000001.0', 1)
                break
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        target = sorted((dst / "decisions").glob("*.json"))[0]
        target.write_text(
            target.read_text(encoding="utf-8").replace('"', "'", 1),
            encoding="utf-8")
    return dst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=str(DEMO_BASE_DEFAULT),
                        help="funds directory (default: outside the repo)")
    parser.add_argument("--fund-id", default="demo_synthetic")
    parser.add_argument("--tamper-ledger", action="store_true",
                        help="also write <id>_tampered with a corrupted ledger")
    parser.add_argument("--tamper-sidecar", action="store_true",
                        help="also write <id>_tampered with a corrupted sidecar")
    args = parser.parse_args(argv)
    base = Path(args.base)
    existing = base / args.fund_id
    if existing.exists():
        shutil.rmtree(existing)  # the generator is IDEMPOTENT
    if base.resolve() == Path.cwd().resolve():
        print("refusing: --base must not be the repo/cwd", file=sys.stderr)
        return 2
    path = build_demo_fund(base, args.fund_id)
    print(f"demo fund written: {path}")
    if args.tamper_ledger:
        print(f"tampered copy: {tampered_copy(base, args.fund_id, 'ledger')}")
    if args.tamper_sidecar:
        print(f"tampered copy: {tampered_copy(base, args.fund_id, 'sidecar')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
