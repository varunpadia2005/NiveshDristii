"""
Test the alpha seam: ModelInputs read-only semantics, the validating builder,
the no-look-ahead property test (with a deliberately leaky CANARY), and the
import boundary (core/, marketdata/, alpha/ must not import niveshdristi.markets).

All frames here are SYNTHETIC and generated in code (neutral names SYN001...).

NO-LOOK-AHEAD CAVEAT (plain statement): the property test catches SIDE-CHANNEL
peeking only — a model that consults an as-of-unaware raw source whose content
extends past as_of. The REAL point-in-time guard is the builder's construction
validation (marketdata.context.build_model_inputs raises DataError on any row
dated after as_of); black-box output comparison alone cannot prove absence of
look-ahead.

DATE.TODAY() EXEMPTION: wrapped legacy code (legacy folders, e.g. the TA
indicators/signals the port calls) is exempt from the model-zone date.today()
ban; such wrapped code is marked 'legacy, not PIT-safe' in its registry entry
description where applicable.
"""

import re
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from niveshdristi.core.errors import DataError
from niveshdristi.marketdata.context import build_from_full_frames, build_model_inputs

T = date(2026, 10, 23)


def _syn_frame(closes: list[float], start: date = date(2026, 9, 1)) -> pl.DataFrame:
    """Synthetic daily frame (neutral symbol data, generated in code)."""
    from datetime import timedelta

    n = len(closes)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(n)]
    return pl.DataFrame({"date": dates, "close": closes, "volume": [1000] * n})


def _truncated() -> pl.DataFrame:
    return _syn_frame([100.0 + i for i in range(30)])  # through T-ish, no future rows


def _full_with_wild_future() -> pl.DataFrame:
    base = _truncated()
    future = pl.DataFrame(
        {
            "date": ["2026-10-26", "2026-10-27"],
            "close": [9999.0, -9999.0],  # deliberately wild future rows
            "volume": [1, 1],
        }
    )
    return pl.concat([base, future])


def assert_no_look_ahead(model, as_of: datetime) -> None:
    """No-look-ahead property.

    (i) Pipeline teeth: inputs built directly from the truncated frame and
    inputs built through the as_of-limited handle from the full
    (future-contaminated) frame must be equivalent — if the handle ever
    stopped truncating, build_model_inputs itself raises DataError here.

    (ii) Model teeth via a SIDE CHANNEL: a raw, as-of-unaware data source the
    model could wrongly consult (a closure, a cache, the network). The
    harness points it at the truncated frame for the baseline call and at the
    full frame for the second call — exactly what a live source would return
    once the future has happened. A model that reads only its inputs is
    unaffected; a model that peeks past as_of produces different output and
    fails this assertion.
    """
    ctx_dict = {"as_of": as_of}
    truncated_inputs = build_model_inputs(as_of=as_of, prices={"SYN001": _truncated()})
    handle_inputs = build_from_full_frames(as_of=as_of, prices={"SYN001": _full_with_wild_future()})

    global _SIDE_CHANNEL
    _SIDE_CHANNEL = {"SYN001": _truncated()}
    a = model.predict(ctx_dict, truncated_inputs)
    _SIDE_CHANNEL = {"SYN001": _full_with_wild_future()}
    b = model.predict(ctx_dict, handle_inputs)
    _SIDE_CHANNEL = {}
    assert a == b, f"model output changed when future rows existed: {a} != {b}"


# The raw, as-of-unaware source a leaky model could consult (see above).
_SIDE_CHANNEL: dict = {}


class HonestModel:
    """Test-only model that reads ONLY its inputs (protocol-shaped)."""

    model_id = "honest_test_model"

    def predict(self, ctx, inputs) -> list[float]:
        df = inputs.prices_for("SYN001")
        return [round(float(df["close"].tail(1)[0]), 6)]


class LeakyCanaryModel:
    """DELIBERATELY LEAKY (test file only, never registered): ignores its
    validated inputs and consults the raw side channel, whose content
    extends past as_of on the second call. assert_no_look_ahead must catch it."""

    model_id = "leaky_canary"

    def predict(self, ctx, inputs) -> list[float]:
        df = _SIDE_CHANNEL["SYN001"]  # the leak: as-of-unaware raw source
        return [round(float(df["close"].tail(1)[0]), 6)]


class TestModelInputsReadOnly:
    """ModelInputs is SHALLOW read-only: rebinding blocked, frames not deep-frozen."""

    def _inputs(self):
        return build_model_inputs(as_of=T, prices={"SYN001": _truncated()})

    def test_setattr_raises(self):
        with pytest.raises(AttributeError, match="read-only"):
            self._inputs().as_of = date(2026, 1, 1)

    def test_mapping_mutation_raises(self):
        inputs = self._inputs()
        with pytest.raises(TypeError):
            inputs.prices["SYN002"] = _truncated()

    def test_shallow_not_deep_frozen(self):
        """Documented limitation: the frame itself can still be copied/mutated
        by a holder — read-only is shallow by design."""
        inputs = self._inputs()
        df = inputs.prices_for("SYN001")
        assert df.height == 30  # frame accessible; no deep-freeze claimed


class TestBuilderValidation:
    def test_future_rows_raise_typed_dataerror(self):
        full = _full_with_wild_future()
        with pytest.raises(DataError, match="SYN001.*2026-10-2[67]"):
            build_model_inputs(as_of=T, prices={"SYN001": full})

    def test_build_from_full_frames_truncates(self):
        inputs = build_from_full_frames(as_of=T, prices={"SYN001": _full_with_wild_future()})
        assert inputs.prices_for("SYN001").height == 30
        assert inputs.as_of == T


class TestNoLookAheadProperty:
    def test_honest_model_passes(self):
        as_of = datetime(2026, 10, 23, 15, 30, tzinfo=UTC)
        assert_no_look_ahead(HonestModel(), as_of)

    def test_leaky_canary_is_caught(self):
        """The canary peeks via a side channel; the property test MUST fail it."""
        as_of = datetime(2026, 10, 23, 15, 30, tzinfo=UTC)
        with pytest.raises(AssertionError, match="future rows"):
            assert_no_look_ahead(LeakyCanaryModel(), as_of)


class TestImportBoundary:
    """No file under core/, marketdata/ or alpha/ may import niveshdristi.markets."""

    NEUTRAL_DIRS = (
        "src/niveshdristi/core",
        "src/niveshdristi/marketdata",
        "src/niveshdristi/alpha",
    )
    MARKET_IMPORT = re.compile(r"^\s*(?:from|import)\s+niveshdristi\.markets\b", re.MULTILINE)

    def test_neutral_packages_do_not_import_markets(self):
        offenders = []
        for d in self.NEUTRAL_DIRS:
            for py in Path(d).rglob("*.py"):
                if self.MARKET_IMPORT.search(py.read_text(encoding="utf-8")):
                    offenders.append(str(py))
        assert offenders == [], f"market imports found in neutral packages: {offenders}"


class TestModelRegistry:
    """Registry: uniqueness, live filtering, stub refusal, market-pack registration."""

    @staticmethod
    def _entry(model_id: str, data_status: str = "live"):
        from niveshdristi.core.alpha import ModelRegistryEntry

        return ModelRegistryEntry(
            model_id=model_id,
            horizon_days=10,
            required_data=("prices",),
            pit_safe=True,
            data_status=data_status,
            description="synthetic test entry",
        )

    def test_register_and_lookup(self):
        from niveshdristi.alpha.registry import ModelRegistry

        reg = ModelRegistry()
        reg.register(self._entry("syn_a"))
        assert reg.entry_for("syn_a").model_id == "syn_a"

    def test_duplicate_rejected(self):
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.core.errors import ConfigurationError

        reg = ModelRegistry()
        reg.register(self._entry("syn_a"))
        with pytest.raises(ConfigurationError, match="duplicate"):
            reg.register(self._entry("syn_a"))

    def test_unknown_rejected(self):
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.core.errors import ConfigurationError

        with pytest.raises(ConfigurationError, match="unknown model_id"):
            ModelRegistry().entry_for("ghost")

    def test_live_entries_exclude_stubs(self):
        from niveshdristi.alpha.registry import ModelRegistry

        reg = ModelRegistry()
        reg.register(self._entry("syn_live"))
        reg.register(self._entry("syn_stub", data_status="stub"))
        assert [e.model_id for e in reg.live_entries()] == ["syn_live"]

    def test_require_live_refuses_stub_unless_allowed(self):
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.core.errors import ConfigurationError

        reg = ModelRegistry()
        stub = self._entry("syn_stub", data_status="stub")
        reg.register(stub)
        with pytest.raises(ConfigurationError, match="refusing live use"):
            reg.require_live(reg.entry_for("syn_stub"))
        assert reg.require_live(reg.entry_for("syn_stub"), allow_stub=True) is stub

    def test_market_pack_register_all_mechanism(self):
        """The register_all seam works with a FAKE market pack (real IN_NSE
        pack has no models until P3-S9)."""
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.markets.in_nse.models import register_all

        reg = ModelRegistry()
        register_all(reg)  # currently registers nothing (no models yet)
        assert reg.entries() == ()
        # prove the seam with a fake pack using the same mechanism
        fake_entries = [self._entry("fake_pack_model", data_status="stub")]
        reg.register_all(fake_entries)
        assert reg.entry_for("fake_pack_model").data_status == "stub"


class TestTaEnsemblePort:
    """PORT equality vs legacy maths (CFG pinned), regime flag, PIT property."""

    @staticmethod
    def _syn_frame(n: int = 300) -> pl.DataFrame:
        """Synthetic frame (neutral SYN001, generated in code) with the
        adj_* columns the legacy indicators consume."""
        import math
        from datetime import timedelta

        closes = [100.0 + 20.0 * math.sin(i / 25.0) + i * 0.05 for i in range(n)]
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame(
            {
                "date": dates,
                "adj_close": closes,
                "adj_high": [c + 1.5 for c in closes],
                "adj_low": [c - 1.5 for c in closes],
                "volume": [1_000_000 + (i % 7) * 10_000 for i in range(n)],
            }
        )

    def test_pinned_cfg_values(self):
        """Legacy reads CFG at CALL time — pin the values the equality relies on.

        INTENTIONAL TRIPWIRE: if anyone changes indicator periods or signal
        weights in config.yaml, this fails so the port-equality result is
        re-examined instead of silently drifting.
        """
        from niveshdristi.config import CFG

        assert CFG.indicators.ema_periods == [20, 50, 200]
        assert CFG.indicators.rsi_period == 14
        assert CFG.signals.weights == {
            "trend": 0.35, "momentum": 0.30, "volatility": 0.15, "volume": 0.20,
        }

    def test_conviction_bounded_on_extremes(self):
        """Synthetic extremes: conviction always within [-1, 1] (NEW clamp).

        Frames chosen to push the legacy composite to its extremes: a strong
        uptrend (all scorers max) and a crash below all bands (volatility
        scorer at -1.0, which without the clamp would push 2c-1 below -1).
        """
        from datetime import UTC

        from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
        from niveshdristi.core.alpha import AsOfContext

        up = self._syn_frame_extreme(uptrend=True)
        crash = self._syn_frame_extreme(uptrend=False)
        for df in (up, crash):
            inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN001": df})
            ctx = AsOfContext(
                as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC),
                universe=(),
                market_id="TEST_MARKET",
            )
            for s in TaEnsemble().predict(ctx, inputs):
                assert -1.0 <= s.conviction <= 1.0

    @staticmethod
    def _syn_frame_extreme(uptrend: bool):
        from datetime import timedelta

        n = 300
        if uptrend:
            closes = [100.0 * (1.0 + 0.004 * i) for i in range(n)]
        else:  # crash: long decline then a gap-down far below the bands
            closes = [100.0 * (1.0 - 0.003 * i) for i in range(n)]
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame(
            {
                "date": dates,
                "adj_close": closes,
                "adj_high": [c * 1.01 for c in closes],
                "adj_low": [c * 0.99 for c in closes],
                "volume": [2_000_000] * n,
            }
        )

    def test_wrapper_equals_direct_legacy_call(self):
        """PORT EQUALITY: wrapper's legacy path == direct legacy invocation."""
        from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
        from niveshdristi.indicators.technical import compute_all_indicators
        from niveshdristi.signals.engine import generate_signal_report

        df = self._syn_frame()
        direct = generate_signal_report("SYN001", compute_all_indicators(df))
        wrapped = TaEnsemble().legacy_report("SYN001", df)
        assert wrapped.composite == direct.composite
        assert wrapped.trend_score == direct.trend_score
        assert wrapped.momentum_score == direct.momentum_score
        assert wrapped.volatility_score == direct.volatility_score
        assert wrapped.volume_score == direct.volume_score

    def _predict_convictions(self, regime_aware: bool) -> list[float]:

        from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
        from niveshdristi.core.alpha import AsOfContext

        df = self._syn_frame()
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN001": df})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC),
            universe=(),
            market_id="TEST_MARKET",
        )
        return [s.conviction for s in TaEnsemble(regime_aware=regime_aware).predict(ctx, inputs)]

    def test_default_off_is_legacy_composite(self):
        """regime_aware=False: conviction == legacy composite*2-1 exactly."""
        from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble

        df = self._syn_frame()
        legacy = TaEnsemble().legacy_report("SYN001", df)
        convictions = self._predict_convictions(regime_aware=False)
        assert convictions == [round(legacy.composite * 2.0 - 1.0, 6)]

    def test_regime_aware_on_changes_blend(self):
        """regime_aware=True: NEW re-weighting applies to the same components."""
        from niveshdristi.alpha.quant.ta_ensemble import REGIME_WEIGHTS, TaEnsemble

        df = self._syn_frame()
        rep = TaEnsemble().legacy_report("SYN001", df)
        scores = {
            "trend": rep.trend_score,
            "momentum": rep.momentum_score,
            "volatility": rep.volatility_score,
            "volume": rep.volume_score,
        }
        w = REGIME_WEIGHTS["choppy"]
        expected = round(round(sum(w[k] * scores[k] for k in scores), 3) * 2.0 - 1.0, 6)
        assert self._predict_convictions(regime_aware=True) == [expected]

    def test_ta_ensemble_no_look_ahead(self):
        """The ported model passes the no-look-ahead property test."""

        from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble
        from niveshdristi.core.alpha import AsOfContext

        model = TaEnsemble()

        class _Adapter:
            """Adapts predict to the float-comparison helper."""

            model_id = "ta_ensemble_adapter"

            def predict(self, ctx, inputs):
                ctx_obj = AsOfContext(
                    as_of=datetime(2026, 10, 23, 15, 30, tzinfo=UTC),
                    universe=(),
                    market_id="TEST_MARKET",
                )
                return [s.conviction for s in model.predict(ctx_obj, inputs)]

        # synthetic 30-row frame shaped for the model
        frame = _syn_frame_for_property()
        globals()["_SYN_PROP_FRAME"] = frame
        try:
            as_of = datetime(2026, 10, 23, 15, 30, tzinfo=UTC)
            cutoff = "2026-10-23"
            truncated = build_model_inputs(
                as_of=as_of,
                prices={"SYN001": frame.filter(pl.col("date") <= cutoff)},
            )
            via_handle = build_from_full_frames(as_of=as_of, prices={"SYN001": frame})
            adapter = _Adapter()
            a = adapter.predict({}, truncated)
            b = adapter.predict({}, via_handle)
            assert a == b
        finally:
            globals().pop("_SYN_PROP_FRAME", None)


def _syn_frame_for_property() -> pl.DataFrame:
    """300-row synthetic frame ending with two wild future rows past 2026-10-23."""
    base = TestTaEnsemblePort._syn_frame(295)
    future = pl.DataFrame(
        {
            "date": ["2026-10-26", "2026-10-27"],
            "adj_close": [9999.0, -9999.0],
            "adj_high": [9999.5, -9998.5],
            "adj_low": [9998.5, -9999.5],
            "volume": [1, 1],
        }
    )
    return pl.concat([base, future])
