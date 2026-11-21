"""P16-A-1 (15-V F-g): the signals blend must have substance.

The 15-V mutation `blended = {}` escaped test_generate_reports_models_
and_blend because its assertions were vacuous (an empty dict IS a dict
and all() over an empty iterable is True). This file pins the blend
substance: non-empty, symbol keys, finite values in [-1, 1], and
equality with a recomputation through the same pipeline.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import polars as pl
from typer.testing import CliRunner

from niveshdristi.cli.main import (
    _data_client_for,
    _live_models_bundle,
    _require_prices,
)
from niveshdristi.core.alpha import AsOfContext
from niveshdristi.engine.advance import ModelBundle
from niveshdristi.marketdata.context import build_from_full_frames
from niveshdristi.portfolio.blending import blend_convictions

REPO = Path(__file__).resolve().parent.parent


def _fake_frame(days: int, end: date) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=days, freq="D")
    n = len(idx)
    return pd.DataFrame(
        {"Open": [100.0 + i for i in range(n)],
         "High": [101.0 + i for i in range(n)],
         "Low": [99.0 + i for i in range(n)],
         "Close": [100.5 + i for i in range(n)],
         "Volume": [1_000_000] * n},
        index=idx,
    )


def _install_fake(monkeypatch) -> date:
    """Patch the IN_NSE adapter's _fetch (no network). Returns the as_of
    date used for the CLI call AND the recompute (same patched fetch)."""
    import niveshdristi.markets.in_nse.providers.yfinance_adapter as yfa

    as_of = date.today() - timedelta(days=3)

    def fake_fetch(provider_symbol, start, end, auto_adjust):
        return _fake_frame(40, as_of)

    monkeypatch.setattr(yfa.YFinanceClient, "_fetch", staticmethod(fake_fetch))
    return as_of


def _invoke_generate(as_of: date) -> dict:
    from niveshdristi.cli.main import app

    r = CliRunner().invoke(
        app,
        ["--json", "signals", "generate", "RELIANCE",
         "--as-of", as_of.isoformat()],
    )
    assert r.exit_code == 0, r.output
    data: dict = json.loads(r.output)
    return data


class TestBlendSubstance:
    """P16-A-1 (15-V F-g): the signals blend must have substance.

    The 15-V mutation `blended = {}` escaped
    test_generate_reports_models_and_blend because its assertions were
    vacuous (an empty dict IS a dict and all() over an empty iterable
    is True). Blend semantics are symbol -> conviction
    (portfolio/blending.py), so keys are asserted against the ticker
    symbol, not model ids (deviation from the 15-V brief recorded in
    the P16-A report section G).
    """

    def test_blend_non_empty_finite_in_range_keys_are_symbols(
        self, monkeypatch
    ):
        data = _invoke_generate(_install_fake(monkeypatch))
        blended = data["blended"]
        assert blended, "the blend must be non-empty (P16-A-1)"
        assert set(blended) <= {data["ticker"]}, (
            f"blend keys must be symbols of the fetched ticker, "
            f"got {set(blended)}"
        )
        for v in blended.values():
            assert isinstance(v, (int, float)), f"blend value must be a number, got {v!r}"
            assert math.isfinite(v), f"blend value must be finite, got {v!r}"
            assert -1.0 <= v <= 1.0, f"blend value out of [-1,1]: {v!r}"

    def test_reported_blend_equals_recomputed_pipeline(
        self, monkeypatch
    ):
        as_of = _install_fake(monkeypatch)
        data = _invoke_generate(as_of)
        as_of_d = date.fromisoformat(data["as_of"])
        bundle = ModelBundle(_live_models_bundle())
        client = _data_client_for(data["market"])
        max_hist = max(
            (getattr(m, "min_history_sessions", 0) for m in bundle.models),
            default=0,
        )
        start = as_of_d - timedelta(days=int(max_hist * 1.5))
        adjusted = _require_prices(
            client.prices(data["ticker"], start, as_of_d, as_of=as_of_d),
            data["ticker"], as_of_d,
        )
        model_frame = adjusted.with_columns(
            pl.col("close").alias("adj_close"),
            pl.col("high").alias("adj_high"),
            pl.col("low").alias("adj_low"),
        )
        inputs = build_from_full_frames(
            as_of=as_of_d, prices={data["ticker"]: model_frame}
        )
        signals = []
        for model in bundle.models:
            signals.extend(
                model.predict(
                    AsOfContext(
                        as_of=datetime.combine(as_of_d, time(15, 30), tzinfo=UTC),
                        universe=(), market_id=data["market"],
                    ),
                    inputs,
                )
            )
        recomputed = blend_convictions(
            bundle.as_strategy_models(), signals,
            known_model_ids=bundle.known_ids,
        )
        assert data["blended"] == recomputed, (
            f"reported blend {data['blended']} != recomputed {recomputed}"
        )
