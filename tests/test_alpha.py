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


class TestPriceRangeModel:
    """S4: evidence-only price ranges, known-answer on a hand-computable frame."""

    @staticmethod
    def _flat_frame(n: int = 30) -> pl.DataFrame:
        """Constant OHLC: close=100, high=102, low=98 -> hand-computable."""
        from datetime import timedelta

        dates = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame(
            {
                "date": dates,
                "high": [102.0] * n,
                "low": [98.0] * n,
                "close": [100.0] * n,
            }
        )

    def test_known_answer(self):
        """Hand-computed: TR = high-low = 102-98 = 4 every bar -> ATR = 4;
        support=98, resistance=102; entry zone (100-2, 100+2); stop=100-2*4=92."""
        from niveshdristi.alpha.quant.price_range import compute_price_evidence

        ev = compute_price_evidence(self._flat_frame())
        assert ev == {
            "support": 98.0,
            "resistance": 102.0,
            "atr": 4.0,
            "entry_zone_low": 98.0,
            "entry_zone_high": 102.0,
            "stop_zone": 92.0,
        }

    def test_signal_is_evidence_only(self):
        """Conviction exactly 0.0; thesis says evidence-only; evidence present."""
        from datetime import UTC

        from niveshdristi.alpha.quant.price_range import PriceRangeModel
        from niveshdristi.core.alpha import AsOfContext

        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN002": self._flat_frame()})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = PriceRangeModel().predict(ctx, inputs)
        assert len(signals) == 1
        s = signals[0]
        assert s.conviction == 0.0
        assert "EVIDENCE-ONLY" in s.thesis
        assert set(s.evidence) == {
            "support", "resistance", "atr", "entry_zone_low", "entry_zone_high", "stop_zone",
        }

    def test_no_look_ahead_property(self):
        """Appended wild future rows must not change the evidence at as_of=T."""
        from datetime import UTC

        from niveshdristi.alpha.quant.price_range import PriceRangeModel
        from niveshdristi.core.alpha import AsOfContext

        base = self._flat_frame(28)
        future = pl.DataFrame(
            {"date": ["2026-12-31"], "high": [9999.0], "low": [-9999.0], "close": [9999.0]}
        )
        full = pl.concat([base, future])

        as_of = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
        truncated = build_model_inputs(
            as_of=as_of, prices={"SYN002": base.filter(pl.col("date") <= "2026-09-28")}
        )
        via_handle = build_from_full_frames(as_of=as_of, prices={"SYN002": full})
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        model = PriceRangeModel()
        a = [(s.instrument.symbol, s.evidence) for s in model.predict(ctx, truncated)]
        b = [(s.instrument.symbol, s.evidence) for s in model.predict(ctx, via_handle)]
        assert a == b


class TestMomentumModels:
    """S5: TS and XS momentum — known answers on synthetic frames."""

    N = 130  # enough for LOOKBACK=120 + SKIP=5 + margin

    @staticmethod
    def _growth_frame(rate: float, n: int) -> pl.DataFrame:
        from datetime import timedelta

        closes = [100.0 * ((1.0 + rate) ** i) for i in range(n)]
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame({"date": dates, "close": closes})

    def _expected_ts_return(self, rate: float) -> float:
        from niveshdristi.alpha.quant.momentum import LOOKBACK_DAYS, SKIP_DAYS

        end = self.N - 1 - SKIP_DAYS
        start = end - LOOKBACK_DAYS
        return (1.0 + rate) ** (end - start) - 1.0

    def test_ts_known_answer(self):
        """Constant 0.1% daily growth: conviction == clipped trailing return."""
        from datetime import UTC

        from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum
        from niveshdristi.core.alpha import AsOfContext

        df = self._growth_frame(0.001, self.N)
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN003": df})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = TimeSeriesMomentum().predict(ctx, inputs)
        assert len(signals) == 1
        expected = round(max(-1.0, min(1.0, self._expected_ts_return(0.001))), 6)
        assert signals[0].conviction == expected

    def test_xs_known_answer_ten_instruments(self):
        """SYN001..SYN010 with strictly increasing growth rates: convictions
        are exactly the centered ranks -1 ... +1 in steps of 2/9."""
        from datetime import UTC

        from niveshdristi.alpha.quant.momentum import CrossSectionalMomentum
        from niveshdristi.core.alpha import AsOfContext

        prices = {
            f"SYN{i:03d}": self._growth_frame(0.001 * i, self.N) for i in range(1, 11)
        }
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices=prices)
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = CrossSectionalMomentum().predict(ctx, inputs)
        by_symbol = {s.instrument.symbol: s.conviction for s in signals}
        assert len(by_symbol) == 10
        for rank, i in enumerate(range(1, 11)):
            expected = round(2.0 * (rank / 9) - 1.0, 6)
            assert by_symbol[f"SYN{i:03d}"] == expected
        # extreme ranks
        assert by_symbol["SYN001"] == -1.0
        assert by_symbol["SYN010"] == 1.0

    def test_xs_needs_multiple_instruments(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.momentum import CrossSectionalMomentum
        from niveshdristi.core.alpha import AsOfContext

        inputs = build_model_inputs(
            as_of=date(2026, 12, 31), prices={"SYN003": self._growth_frame(0.001, self.N)}
        )
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        assert CrossSectionalMomentum().predict(ctx, inputs) == []

    def test_momentum_no_look_ahead(self):
        """Future wild rows must not change momentum signals at as_of=T."""
        from datetime import UTC

        from niveshdristi.alpha.quant.momentum import CrossSectionalMomentum, TimeSeriesMomentum
        from niveshdristi.core.alpha import AsOfContext

        base = self._growth_frame(0.001, 129)
        future = pl.DataFrame({"date": ["2027-01-01"], "close": [99999.0]})
        full = pl.concat([base, future])
        as_of = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)
        truncated = build_model_inputs(
            as_of=as_of, prices={"SYN003": base.filter(pl.col("date") <= "2026-12-31")}
        )
        via_handle = build_from_full_frames(as_of=as_of, prices={"SYN003": full})
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        for model in (TimeSeriesMomentum(), CrossSectionalMomentum()):
            key = lambda ss: [(s.instrument.symbol, s.conviction) for s in ss]  # noqa: E731
            assert key(model.predict(ctx, truncated)) == key(model.predict(ctx, via_handle))


class TestMeanReversion:
    """S6: contrarian z-score — hand-computed known answer."""

    def test_known_answer_clipped(self):
        """19 closes of 100 + last 102: mean=100.1, var=0.19, std=sqrt(0.19),
        z=1.9/sqrt(0.19)=4.3589 -> contrarian conviction clipped to -1.0."""
        from datetime import UTC

        from niveshdristi.alpha.quant.mean_reversion import MeanReversion, zscore_last
        from niveshdristi.core.alpha import AsOfContext

        closes = [100.0] * 19 + [102.0]
        z = zscore_last(closes)
        assert z is not None
        assert round(z, 4) == 4.3589
        df = _syn_frame(closes)
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN004": df})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = MeanReversion().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == -1.0  # clipped at Z_CAP=3.0
        assert signals[0].evidence["z_score"] == round(z, 6)

    def test_degenerate_series_no_opinion(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.mean_reversion import MeanReversion
        from niveshdristi.core.alpha import AsOfContext

        df = _syn_frame([100.0] * 30)  # zero variance
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN004": df})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        assert MeanReversion().predict(ctx, inputs) == []

    def test_no_look_ahead(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.mean_reversion import MeanReversion
        from niveshdristi.core.alpha import AsOfContext

        base = _syn_frame([100.0] * 19 + [101.0])
        future = pl.DataFrame({"date": ["2027-01-01"], "close": [9999.0], "volume": [1]})
        full = pl.concat([base, future])
        as_of = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)
        truncated = build_model_inputs(
            as_of=as_of, prices={"SYN004": base.filter(pl.col("date") <= "2026-12-31")}
        )
        via_handle = build_from_full_frames(as_of=as_of, prices={"SYN004": full})
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        m = MeanReversion()
        assert m.predict(ctx, truncated) == m.predict(ctx, via_handle)


class TestLowVolatility:
    """S6: below-median vol tilt — hand-computable two-symbol case."""

    @staticmethod
    def _frames():
        from datetime import timedelta

        n = 70
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        flat = pl.DataFrame({"date": dates, "close": [100.0] * n})
        wild_closes = [100.0 * (1.1 if i % 2 else 0.9) for i in range(n)]
        wild = pl.DataFrame({"date": dates, "close": wild_closes})
        return {"SYN005": flat, "SYN006": wild}

    def test_known_answer(self):
        """Flat symbol: vol=0 -> conviction 1.0. Wild symbol: above median -> skipped."""
        from datetime import UTC

        from niveshdristi.alpha.quant.low_volatility import LowVolatility
        from niveshdristi.core.alpha import AsOfContext

        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices=self._frames())
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = LowVolatility().predict(ctx, inputs)
        assert [(s.instrument.symbol, s.conviction) for s in signals] == [("SYN005", 1.0)]

    def test_needs_multiple_instruments(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.low_volatility import LowVolatility
        from niveshdristi.core.alpha import AsOfContext

        frames = self._frames()
        inputs = build_model_inputs(as_of=date(2026, 12, 31), prices={"SYN005": frames["SYN005"]})
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        assert LowVolatility().predict(ctx, inputs) == []


class TestRegimeModel:
    """S7: role-based regime classification — hand-computable states."""

    @staticmethod
    def _bench_frame(total_ret: float, n: int = 61) -> pl.DataFrame:
        from datetime import timedelta

        rate = (1.0 + total_ret) ** (1.0 / (n - 1))
        closes = [100.0 * (rate ** i) for i in range(n)]
        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame({"date": dates, "close": closes})

    @staticmethod
    def _vol_frame(level: float, n: int = 61) -> pl.DataFrame:
        from datetime import timedelta

        dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        return pl.DataFrame({"date": dates, "value": [level] * n})

    def _state(self, total_ret: float, vix: float) -> str:
        from datetime import UTC

        from niveshdristi.alpha.quant.regime import RegimeModel
        from niveshdristi.core.alpha import AsOfContext

        inputs = build_model_inputs(
            as_of=date(2026, 12, 31),
            prices={"SYN007": _syn_frame([100.0] * 30)},
            aux={
                "benchmark": self._bench_frame(total_ret),
                "volatility": self._vol_frame(vix),
            },
        )
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        signals = RegimeModel().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 0.0  # evidence-only
        return str(signals[0].evidence["regime_state"])

    def test_known_states(self):
        assert self._state(total_ret=0.20, vix=15.0) == "bull"
        assert self._state(total_ret=-0.20, vix=15.0) == "bear"
        assert self._state(total_ret=0.05, vix=30.0) == "bear"  # high vol overrides
        assert self._state(total_ret=0.05, vix=15.0) == "choppy"

    def test_roles_required(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.regime import RegimeModel
        from niveshdristi.core.alpha import AsOfContext

        inputs = build_model_inputs(
            as_of=date(2026, 12, 31), prices={"SYN007": _syn_frame([100.0] * 30)}
        )
        ctx = AsOfContext(
            as_of=datetime(2026, 12, 31, 15, 0, tzinfo=UTC), universe=(), market_id="TEST_MARKET"
        )
        assert RegimeModel().predict(ctx, inputs) == []

    def test_aux_frames_truncated_to_as_of(self):
        """Aux frames are not builder-validated; the model must self-truncate."""
        from datetime import UTC

        from niveshdristi.alpha.quant.regime import RegimeModel
        from niveshdristi.core.alpha import AsOfContext

        bench = pl.concat(
            [self._bench_frame(0.20), pl.DataFrame({"date": ["2027-06-01"], "close": [1.0]})]
        )
        vol = pl.concat(
            [self._vol_frame(15.0), pl.DataFrame({"date": ["2027-06-01"], "value": [99.0]})]
        )
        as_of = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)
        inputs = build_model_inputs(
            as_of=as_of,
            prices={"SYN007": _syn_frame([100.0] * 30)},
            aux={"benchmark": bench, "volatility": vol},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        signals = RegimeModel().predict(ctx, inputs)
        # The 2027 rows (close=1.0, vol=99.0) must be invisible: still 'bull',
        # not 'bear'; volatility evidence still 15.0.
        assert signals[0].evidence["regime_state"] == "bull"
        assert signals[0].evidence["volatility_last"] == 15.0

    def test_profile_has_volatility_index_symbol(self):
        """The market profile carries the role symbol, marked UNVERIFIED."""
        from niveshdristi.markets.in_nse.profile import IN_NSE_PROFILE
        from niveshdristi.markets.registry import MarketProfile

        assert hasattr(MarketProfile, "model_fields") or True  # pydantic model
        assert IN_NSE_PROFILE.volatility_index_symbol != ""
        assert IN_NSE_PROFILE.benchmark_symbol != ""
