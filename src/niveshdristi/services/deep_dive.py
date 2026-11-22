"""Stock Deep-Dive + Compare (NEW, P8-S7).

Candles and indicator panes from STORED SNAPSHOT frames via the TA
ensemble wrapper; per-model leans from snapshot_signals; risk-gate verdicts
ONLY from the recorded sidecar clamp log (never recomputed); entry/stop
zones from the price-range evidence function, labelled evidence-only.
Guardrails/fundamentals: unavailable (no verified source)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _snapshot_frame(paths: Any, as_of: str, symbol: str):
    snap_dir = paths.snapshots / as_of
    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = manifest.get(symbol)
    if not digest:
        return None
    import polars as pl

    matches = sorted(snap_dir.glob(f"{symbol}_{digest[:16]}.parquet"))
    return pl.read_parquet(matches[0]) if matches else None


def deep_dive(symbol: str, fund_id: str, base: str | Path | None = None) -> dict:
    from niveshdristi.alpha.quant.price_range import compute_price_evidence
    from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger
    from niveshdristi.services.fund import read_fund
    from niveshdristi.services.signals_view import snapshot_signals

    paths = FundPaths(base).for_fund(fund_id)
    base_payload = read_fund(fund_id, base=base)
    records = PaperLedger(paths.ledger).records()
    if not records:
        return {**base_payload, "available": False,
                "reason": "no stored sessions"}
    as_of = records[-1]["session_date"]
    frame = _snapshot_frame(paths, as_of, symbol)
    if frame is None:
        return {**base_payload, "available": False,
                "reason": f"no stored snapshot for {symbol} at {as_of}"}

    wrapper = TaEnsemble()
    indicators = wrapper.indicator_frame(frame)
    last = indicators.row(-1, named=True)
    rsi = last.get("rsi")
    macd = last.get("macd")
    macd_hist = last.get("macd_hist")
    ema_50, ema_200 = last.get("ema_50"), last.get("ema_200")
    close = float(last["adj_close"]) if "adj_close" in last else float(last["close"])

    evidence = compute_price_evidence(frame)  # evidence-only zones

    # per-model leans (reuses the S5/S6 machinery for this one symbol)
    signals = snapshot_signals(fund_id, base=base, as_of=as_of)
    per_model = []
    for model in _registered_models():
        status = getattr(model, "data_status", None)
        if status == "stub":
            per_model.append({"model_id": model.model_id,
                              "label": "Stub: not computed"})
            continue
        entry = signals.get(symbol, {})
        per_model.append({
            "model_id": model.model_id,
            "label": entry.get("lean", "No opinion")
            if status != "evidence_only" else "Evidence only",
            "thesis": entry.get("thesis", "") if status != "evidence_only" else "",
        })

    # recorded gate verdicts from the sidecar clamp log (NEVER recomputed)
    sidecar_dir = paths.root / "decisions"
    gate_log: list[dict] = []
    from datetime import date as _date

    from niveshdristi.paper.decisions_sidecar import read_sidecar

    sidecar = read_sidecar(sidecar_dir, _date.fromisoformat(as_of),
                           records[-1]["hash"])
    if sidecar and sidecar["verified"] and sidecar["payload"]:
        pending = sidecar["payload"].get("pending") or {}
        gate_log = list(pending.get("log") or [])

    return {
        **base_payload,
        "available": True,
        "as_of": as_of,
        "symbol": symbol,
        "candles": frame.to_dicts(),
        "indicators": {
            "rsi": rsi, "macd": macd, "macd_hist": macd_hist,
            "ema_50": ema_50, "ema_200": ema_200,
            "ma50_position": ("above 50-day" if ema_50 is not None
                              and close > ema_50 else
                              "below 50-day" if ema_50 is not None else "n/a"),
            "ma200_position": ("above 200-day" if ema_200 is not None
                               and close > ema_200 else
                               "below 200-day" if ema_200 is not None else
                               "n/a (insufficient warmup)"),
        },
        "zones_evidence_only": evidence,
        "per_model": per_model,
        "gate_log": gate_log,
        "unavailable": ["guardrails", "fundamentals checklist"],
    }


def _registered_models() -> list:
    from niveshdristi.services.signals_view import _live_bundle

    return list(_live_bundle().models)


def compare(symbol_a: str, symbol_b: str, fund_id: str,
            base: str | Path | None = None) -> dict:
    """Two stored instruments side by side — indicators, per-model leans,
    recorded gate verdicts. NO action buttons anywhere."""
    a = deep_dive(symbol_a, fund_id, base)
    # P19-LOOK A3: carry the banner fields so render_compare's
    # banner_strip works (was: KeyError 'disclaimer').
    return {"a": a, "b": deep_dive(symbol_b, fund_id, base),
            "banner": a.get("banner"), "rates_banner": a.get("rates_banner"),
            "disclaimer": a.get("disclaimer")}
