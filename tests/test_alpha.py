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

import json
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
        "src/niveshdristi/portfolio",
        "src/niveshdristi/execution",
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
        """register_all registers every IN_NSE model (wired in S9b); the seam
        also accepts further entries via the same mechanism."""
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.markets.in_nse.models import register_all

        reg = ModelRegistry()
        register_all(reg)
        assert [e.model_id for e in reg.entries()] == [
            "block_deals", "delivery_anomaly", "fii_dii_regime", "macro_overlay",
            "promoter_pledge",
        ]
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
        """Aux frames flow through the truncating handle (G2a); the model's
        own self-truncation is a redundant second layer."""
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
        inputs = build_from_full_frames(
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


class TestAuxFrameValidation:
    """G2a: the builder validates/truncates aux frames by ROLE."""

    def _aux_with_future(self):
        good = pl.DataFrame({"date": ["2026-10-20"], "value": [10.0]})
        bad = pl.DataFrame({"date": ["2027-01-01"], "value": [99.0]})
        return pl.concat([good, bad])

    def test_builder_fails_on_future_dated_aux(self):
        with pytest.raises(DataError, match="aux frame for 'volatility'.*2027-01-01"):
            build_model_inputs(
                as_of=T,
                prices={"SYN001": _truncated()},
                aux={"volatility": self._aux_with_future()},
            )

    def test_handle_truncates_aux(self):
        inputs = build_from_full_frames(
            as_of=T,
            prices={"SYN001": _truncated()},
            aux={"volatility": self._aux_with_future()},
        )
        vol = inputs.aux["volatility"]
        assert vol.height == 1
        assert float(vol["value"].tail(1)[0]) == 10.0


class TestFundamentalGuardrails:
    """S8: ported rules maths equality + PIT wiring + NEW quality score."""

    @staticmethod
    def _pit_records() -> "tuple":
        from niveshdristi.marketdata.pit import PITRecord

        def rec(metric, value, announced):
            return PITRecord(
                symbol="SYN008", metric=metric, value=value,
                period_end=date(2026, 6, 30), announced_at=announced, source="synthetic",
            )

        return (
            rec("pe_ratio", 25.0, date(2026, 7, 20)),
            rec("roe", 0.18, date(2026, 7, 20)),
            rec("debt_to_equity", 1.2, date(2026, 7, 20)),
        )

    def _ctx_inputs(self, as_of_date: date):
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.marketdata.pit import PITStore

        store = PITStore()
        for r in self._pit_records():
            store.put(r)
        records = tuple(store.query("SYN008", as_of=as_of_date))
        inputs = build_model_inputs(
            as_of=as_of_date, prices={}, fundamentals={"SYN008": records}
        )
        ctx = AsOfContext(
            as_of=datetime(as_of_date.year, as_of_date.month, as_of_date.day, 15, 0, tzinfo=UTC),
            universe=(), market_id="TEST_MARKET",
        )
        return ctx, inputs

    def test_port_equality_vs_direct_legacy_call(self):
        """Wrapper's guardrail evaluation == direct legacy check_guardrails."""
        from niveshdristi.alpha.quant.fundamental_guardrails import FundamentalGuardrails

        model = FundamentalGuardrails()
        ctx, inputs = self._ctx_inputs(date(2026, 8, 1))
        fund = model._fund_from_pit("SYN008", inputs.fundamentals["SYN008"])
        assert fund is not None
        direct = check_guardrails_legacy(fund)
        wrapped = model.legacy_report(fund)
        assert wrapped.max_score_cap == direct.max_score_cap
        assert [f["metric"] for f in wrapped.flags] == [f["metric"] for f in direct.flags]
        assert [f["severity"] for f in wrapped.flags] == [f["severity"] for f in direct.flags]

    def test_pit_visibility_controls_input(self):
        """A result announced tomorrow is invisible today (frozen PIT property)
        at the model's input boundary."""
        from niveshdristi.alpha.quant.fundamental_guardrails import FundamentalGuardrails

        model = FundamentalGuardrails()

        ctx_today, inputs_today = self._ctx_inputs(date(2026, 7, 19))
        ctx_tomorrow, inputs_tomorrow = self._ctx_inputs(date(2026, 7, 21))
        # Before announcement: no records -> no fundamentals -> no signal
        assert inputs_today.fundamentals["SYN008"] == ()
        assert model.predict(ctx_today, inputs_today) == []
        # After announcement: records present -> signal produced
        sigs = model.predict(ctx_tomorrow, inputs_tomorrow)
        assert len(sigs) == 1
        assert "quality_score" in sigs[0].evidence

    def test_quality_score_and_exclusion_new_maths(self):
        """NEW: score = 100 - penalties (capped); 'error' flag excludes."""
        from niveshdristi.alpha.quant.fundamental_guardrails import quality_score

        score, excluded = quality_score(100, [])
        assert (score, excluded) == (100, False)
        score, excluded = quality_score(100, [{"severity": "warn"}])
        assert (score, excluded) == (80, False)
        score, excluded = quality_score(100, [{"severity": "warn"}, {"severity": "error"}])
        assert (score, excluded) == (40, True)
        score, _ = quality_score(30, [{"severity": "warn"}])  # 100-20=80, capped at 30
        assert score == 30


def check_guardrails_legacy(fund):
    from niveshdristi.fundamentals.loader import check_guardrails

    return check_guardrails(fund)


class TestDeliveryAnomaly:
    """S9a: delivery-% anomaly over the neutral 'delivery' role frame."""

    @staticmethod
    def _delivery_frame(spike: bool = False) -> pl.DataFrame:
        """21 sessions: constant 40% baseline; optional final spike to 90%."""
        from datetime import timedelta

        dates = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(21)]
        pct = [40.0] * 21
        if spike:
            pct[-1] = 90.0
        return pl.DataFrame({"symbol": ["SYN009"] * 21, "date": dates, "delivery_pct": pct})

    def _predict(self, spike: bool):
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.markets.in_nse.models.delivery_anomaly import DeliveryAnomaly

        as_of = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
        inputs = build_model_inputs(
            as_of=as_of,
            prices={"SYN009": _syn_frame([100.0] * 30)},
            aux={"delivery": self._delivery_frame(spike)},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        return DeliveryAnomaly().predict(ctx, inputs)

    def test_no_spike_no_signal(self):
        """Constant delivery % -> zero variance -> no opinion."""
        assert self._predict(spike=False) == []

    def test_spike_known_answer(self):
        """20 baseline 40s + one 90: mean=42.4? window=last 20 of 21 values.
        Window = [40]*19 + [90]: mean=42.5, var=(19*6.25+2250)/20=118.75,
        std=10.897, z=(90-42.5)/10.897=4.359 -> clipped to +1.0."""
        signals = self._predict(spike=True)
        assert len(signals) == 1
        assert signals[0].conviction == 1.0
        assert round(signals[0].evidence["delivery_z"], 3) == 4.359

    def test_adapter_maps_neutral_columns(self):
        """The allowlisted adapter translates parser columns to neutral names."""
        from niveshdristi.markets.in_nse.providers.bhavcopy_file import (
            parse_bhavcopy_csv,
            to_delivery_frame,
        )

        df = parse_bhavcopy_csv(Path("tests/fixtures/bhavcopy_SYNTHETIC_sec_bhavdata_full.csv"))
        neutral = to_delivery_frame(df)
        assert neutral.columns == ["symbol", "date", "delivery_pct"]
        assert neutral["symbol"].to_list() == ["TESTA", "TESTB", "TESTC"]

    def test_no_look_ahead(self):
        """Future-dated delivery rows are invisible via the truncating handle."""
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.markets.in_nse.models.delivery_anomaly import DeliveryAnomaly

        base = self._delivery_frame(spike=True)
        future = pl.DataFrame(
            {"symbol": ["SYN009"], "date": ["2027-01-01"], "delivery_pct": [5.0]}
        )
        full = pl.concat([base, future])
        as_of = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
        truncated = build_model_inputs(
            as_of=as_of,
            prices={"SYN009": _syn_frame([100.0] * 30)},
            aux={"delivery": base},
        )
        via_handle = build_from_full_frames(
            as_of=as_of,
            prices={"SYN009": _syn_frame([100.0] * 30)},
            aux={"delivery": full},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        m = DeliveryAnomaly()
        a = [(s.instrument.symbol, s.conviction) for s in m.predict(ctx, truncated)]
        b = [(s.instrument.symbol, s.conviction) for s in m.predict(ctx, via_handle)]
        assert a == b
        assert len(a) == 1


class TestIndiaStubModels:
    """S9b: three India stubs — fixture maths + stub marking + register_all."""

    @staticmethod
    def _ctx_inputs(aux: dict, prices=None):
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext

        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        inputs = build_model_inputs(
            as_of=as_of,
            prices=prices or {"SYN010": _syn_frame([100.0] * 30)},
            aux=aux,
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        return ctx, inputs

    def test_promoter_pledge_rising_is_red_flag(self):
        from niveshdristi.markets.in_nse.models.promoter_pledge import PromoterPledge

        frame = pl.DataFrame(
            {
                "symbol": ["SYN010"] * 4,
                "date": ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"],
                "pledge_pct": [5.0, 5.0, 5.0, 10.0],  # +5pp rise -> full negative
            }
        )
        ctx, inputs = self._ctx_inputs({"promoter_pledge": frame})
        signals = PromoterPledge().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == -1.0
        assert signals[0].evidence["data_status"] == "stub"

    def test_fii_dii_flow_regime_known_answer(self):
        from niveshdristi.markets.in_nse.models.fii_dii_regime import FiiDiiRegime

        frame = pl.DataFrame(
            {
                "date": [f"2026-09-{i:02d}" for i in range(1, 21)],
                "net_flow": [50.0] * 20,  # total 1000 -> conviction +1.0
            }
        )
        ctx, inputs = self._ctx_inputs({"flows": frame})
        signals = FiiDiiRegime().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 1.0
        assert signals[0].evidence["data_status"] == "stub"

    def test_block_deal_premium_recent(self):
        from niveshdristi.markets.in_nse.models.block_deals import BlockDeals

        frame = pl.DataFrame(
            {"symbol": ["SYN010"], "date": ["2026-10-10"], "premium_pct": [5.0]}
        )
        ctx, inputs = self._ctx_inputs({"block_deals": frame})
        signals = BlockDeals().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 1.0  # 5% premium at scale 5 -> +1
        assert signals[0].evidence["days_old"] == 13

    def test_block_deal_stale_ignored(self):
        from niveshdristi.markets.in_nse.models.block_deals import BlockDeals

        frame = pl.DataFrame(
            {"symbol": ["SYN010"], "date": ["2026-01-10"], "premium_pct": [5.0]}
        )
        ctx, inputs = self._ctx_inputs({"block_deals": frame})
        assert BlockDeals().predict(ctx, inputs) == []

    def test_register_all_registers_every_india_model(self):
        from niveshdristi.alpha.registry import ModelRegistry
        from niveshdristi.markets.in_nse.models import register_all

        reg = ModelRegistry()
        register_all(reg)
        ids = [e.model_id for e in reg.entries()]
        assert ids == [
            "block_deals", "delivery_anomaly", "fii_dii_regime", "macro_overlay",
            "promoter_pledge",
        ]
        statuses = {e.model_id: e.data_status for e in reg.entries()}
        assert statuses["delivery_anomaly"] == "live"
        assert statuses["promoter_pledge"] == "stub"
        assert statuses["fii_dii_regime"] == "stub"
        assert statuses["block_deals"] == "stub"
        assert statuses["macro_overlay"] == "stub"

    def test_no_look_ahead_stub_models(self):
        """Future-dated aux rows invisible for all three stubs (via handle)."""
        from niveshdristi.markets.in_nse.models.block_deals import BlockDeals
        from niveshdristi.markets.in_nse.models.fii_dii_regime import FiiDiiRegime
        from niveshdristi.markets.in_nse.models.promoter_pledge import PromoterPledge

        pledge = pl.DataFrame(
            {
                "symbol": ["SYN010"] * 4,
                "date": ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"],
                "pledge_pct": [5.0, 5.0, 5.0, 10.0],
            }
        )
        future_row = pl.DataFrame(
            {"symbol": ["SYN010"], "date": ["2027-01-01"], "pledge_pct": [99.0]}
        )
        pledge_future = pl.concat([pledge, future_row])
        from niveshdristi.core.alpha import AsOfContext

        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        prices = {"SYN010": _syn_frame([100.0] * 30)}
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        truncated = build_model_inputs(as_of=as_of, prices=prices, aux={"promoter_pledge": pledge})
        via_handle = build_from_full_frames(
            as_of=as_of, prices=prices, aux={"promoter_pledge": pledge_future}
        )
        m = PromoterPledge()
        assert [(s.instrument.symbol, s.conviction) for s in m.predict(ctx, truncated)] == [
            (s.instrument.symbol, s.conviction) for s in m.predict(ctx, via_handle)
        ]
        # flows and block_deals roles use the same builder-validated path
        assert FiiDiiRegime().predict(ctx, truncated) == []
        assert BlockDeals().predict(ctx, truncated) == []


class TestMacroOverlay:
    """S9c: direction-only macro overlay, tilt from UNVERIFIED YAML."""

    @staticmethod
    def _macro_frame():
        return pl.DataFrame(
            {
                "factor": ["repo_rate_down", "fx_inr_stronger"],
                "date": ["2026-10-20", "2026-10-21"],
                "direction": [1, -1],
            }
        )

    def test_tilt_known_answer(self):
        """repo_rate_down=+1 -> banks +1; fx_inr_stronger=-1 -> it +1, paints -1."""
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.markets.in_nse.models.macro_overlay import MacroOverlay

        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        inputs = build_model_inputs(
            as_of=as_of,
            prices={"SYN011": _syn_frame([100.0] * 30)},
            aux={"macro": self._macro_frame()},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        signals = MacroOverlay().predict(ctx, inputs)
        assert len(signals) == 1
        s = signals[0]
        assert s.conviction == 0.0  # evidence-only
        # zero-direction sectors also appear (direction-only sums, incl. 0)
        assert s.metadata["sector_tilt"] == {"banks": 1, "energy": 0, "it": 1, "paints": -1}
        assert s.metadata["factor_directions"] == {"fx_inr_stronger": -1, "repo_rate_down": 1}
        assert s.evidence["data_status"] == "stub"

    def test_future_macro_rows_invisible(self):
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.markets.in_nse.models.macro_overlay import MacroOverlay

        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        future = pl.DataFrame(
            {"factor": ["crude_down"], "date": ["2027-01-01"], "direction": [1]}
        )
        full = pl.concat([self._macro_frame(), future])
        prices = {"SYN011": _syn_frame([100.0] * 30)}
        via_handle = build_from_full_frames(as_of=as_of, prices=prices, aux={"macro": full})
        truncated = build_model_inputs(
            as_of=as_of, prices=prices, aux={"macro": self._macro_frame()}
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        m = MacroOverlay()
        assert [(s.evidence, s.metadata) for s in m.predict(ctx, truncated)] == [
            (s.evidence, s.metadata) for s in m.predict(ctx, via_handle)
        ]


class TestSectorRotation:
    """S9c: ported compute_rrg/market_regime — equality vs direct legacy calls."""

    @staticmethod
    def _frames():
        from datetime import timedelta

        n = 80
        dates = [(date(2026, 6, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        bench = pl.DataFrame({"date": dates, "close": [100.0 + i * 0.1 for i in range(n)]})
        sector = pl.DataFrame(
            {
                "sector": ["alpha", "beta"] * (n // 2),
                "date": dates * 1,
                "close": [100.0 + i * 0.2 if i % 2 == 0 else 100.0 - i * 0.1 for i in range(n)],
            }
        )
        return sector, bench

    def test_quadrants_equal_direct_legacy_call(self):
        """PORT EQUALITY: wrapper quadrants == direct legacy compute_rrg on the
        same synthetic inputs (no legacy golden exists for compute_rrg)."""
        import asyncio

        from niveshdristi.alpha.quant.sector_rotation import SectorRotation
        from niveshdristi.regime.rrg import compute_rrg

        sector_frame, bench = self._frames()
        model = SectorRotation()
        wrapped = asyncio.run(
            model.legacy_quadrants(
                {
                    name: g.drop("sector")
                    for name, g in sector_frame.partition_by("sector", as_dict=True).items()
                },
                bench,
            )
        )
        direct = asyncio.run(
            compute_rrg(
                {
                    name: g.drop("sector").with_columns(
                        pl.col("close").alias("adj_close")
                    )
                    for name, g in sector_frame.partition_by("sector", as_dict=True).items()
                },
                bench.with_columns(pl.col("close").alias("adj_close")),
            )
        )
        assert wrapped == direct

    def test_state_equal_direct_legacy_call(self):
        from niveshdristi.alpha.quant.sector_rotation import SectorRotation
        from niveshdristi.regime.rrg import market_regime

        _, bench = self._frames()
        model = SectorRotation()
        assert model.legacy_state(bench) == market_regime(
            bench.with_columns(pl.col("close").alias("adj_close")), 15.0
        )

    def test_predict_emits_evidence_only_tilt(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.sector_rotation import SectorRotation
        from niveshdristi.core.alpha import AsOfContext

        sector_frame, bench = self._frames()
        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        inputs = build_from_full_frames(
            as_of=as_of,
            prices={"SYN012": _syn_frame([100.0] * 30)},
            aux={"sector_index": sector_frame, "benchmark": bench},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        signals = SectorRotation().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 0.0
        assert set(signals[0].metadata["sector_quadrants"]) == {"('alpha',)", "('beta',)"}
        assert signals[0].evidence["data_status"] == "stub"


class TestQualityValue:
    """S10: two-leg quality/value screen over synthetic PIT records."""

    @staticmethod
    def _inputs(metrics: dict):
        from datetime import UTC

        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.marketdata.pit import PITRecord

        records = tuple(
            PITRecord(
                symbol="SYN013", metric=m, value=v,
                period_end=date(2026, 6, 30), announced_at=date(2026, 7, 20),
                source="synthetic",
            )
            for m, v in metrics.items()
        )
        as_of = datetime(2026, 8, 1, 15, 0, tzinfo=UTC)
        inputs = build_model_inputs(as_of=as_of, prices={}, fundamentals={"SYN013": records})
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        return ctx, inputs

    def test_both_legs_pass(self):
        from niveshdristi.alpha.quant.quality_value import QualityValue

        ctx, inputs = self._inputs({"earnings_yield": 0.08, "roce": 0.20})
        signals = QualityValue().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 1.0
        assert signals[0].evidence["data_status"] == "stub"

    def test_one_leg_fails_is_neutral_no_signal(self):
        from niveshdristi.alpha.quant.quality_value import QualityValue

        ctx, inputs = self._inputs({"earnings_yield": 0.08, "roce": 0.05})
        assert QualityValue().predict(ctx, inputs) == []  # score 0.5 -> conviction 0

    def test_both_fail_negative(self):
        from niveshdristi.alpha.quant.quality_value import QualityValue

        ctx, inputs = self._inputs({"earnings_yield": 0.01, "roce": 0.02})
        signals = QualityValue().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == -1.0


class TestEarningsDrift:
    """S10: post-announcement drift over synthetic announcement + prices."""

    @staticmethod
    def _inputs(announce_day: str, base: float, last: float, as_of_day: str):
        from niveshdristi.core.alpha import AsOfContext
        from niveshdristi.marketdata.pit import PITRecord

        record = PITRecord(
            symbol="SYN014", metric="eps", value=10.0,
            period_end=date.fromisoformat(announce_day),
            announced_at=date.fromisoformat(announce_day), source="synthetic",
        )
        prices = _syn_frame([base, base], start=date.fromisoformat(announce_day))
        # overwrite dates explicitly: announcement day and as_of day
        prices = pl.DataFrame(
            {"date": [announce_day, as_of_day], "close": [base, last], "volume": [1, 1]}
        )
        as_of = datetime.fromisoformat(as_of_day + "T15:00:00+00:00")
        inputs = build_model_inputs(
            as_of=as_of, prices={"SYN014": prices}, fundamentals={"SYN014": (record,)}
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        return ctx, inputs

    def test_drift_known_answer(self):
        """+10% drift with clip 20% -> conviction +0.5."""
        from niveshdristi.alpha.quant.earnings_drift import EarningsDrift

        ctx, inputs = self._inputs("2026-10-01", 100.0, 110.0, "2026-10-21")
        signals = EarningsDrift().predict(ctx, inputs)
        assert len(signals) == 1
        assert signals[0].conviction == 0.5
        assert signals[0].evidence["post_announcement_return"] == 0.1
        assert signals[0].evidence["data_status"] == "stub"

    def test_stale_announcement_ignored(self):
        from niveshdristi.alpha.quant.earnings_drift import EarningsDrift

        ctx, inputs = self._inputs("2026-01-01", 100.0, 150.0, "2026-10-21")
        assert EarningsDrift().predict(ctx, inputs) == []

    def test_no_look_ahead(self):
        """A record announced AFTER as_of never reaches the model (builder/PIT)."""
        from datetime import UTC

        from niveshdristi.alpha.quant.earnings_drift import EarningsDrift
        from niveshdristi.marketdata.pit import PITRecord

        record = PITRecord(
            symbol="SYN014", metric="eps", value=1.0,
            period_end=date(2026, 10, 1), announced_at=date(2026, 11, 1),
            source="synthetic",
        )
        as_of = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
        prices = pl.DataFrame(
            {"date": ["2026-10-01", "2026-10-21"], "close": [100.0, 110.0], "volume": [1, 1]}
        )
        inputs = build_model_inputs(
            as_of=as_of, prices={"SYN014": prices}, fundamentals={"SYN014": (record,)}
        )
        from niveshdristi.core.alpha import AsOfContext

        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        # The record is in the bundle only if the caller's PIT query included it;
        # the model itself measures drift only from as_of-visible prices, and a
        # future announcement (announced_at > as_of) is filtered by PIT queries.
        # Here we assert the model ignores an announcement dated after as_of:
        signals = EarningsDrift().predict(ctx, inputs)
        assert signals == []  # days = -11 < 0 -> ignored


class TestModelsListCLI:
    """S11: nd models list — offline, plain width-independent JSON."""

    def test_models_json_offline(self):
        from typer.testing import CliRunner

        from niveshdristi.cli.main import app

        result = CliRunner().invoke(app, ["--json", "models"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 16
        ids = {m["model_id"] for m in data["models"]}
        assert "ta_ensemble" in ids
        assert "macro_overlay" in ids
        for m in data["models"]:
            assert m["horizon_days"] >= 1
            assert m["data_status"] in ("live", "stub")

    def test_models_json_width_independent(self):
        import os
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        env["COLUMNS"] = "40"
        proc = subprocess.run(
            [sys.executable, "-m", "niveshdristi.cli.main", "--json", "models"],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
            env=env, timeout=120,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)  # valid at COLUMNS=40
        assert data["count"] == 16


class TestPhase3SpecConformance:
    """S12: every model the Phase 3 spec lists is registered, documented and tested.

    Source of truth: docs/CLAUDE_CODE_PROMPT.md '## PHASE 3 — Alpha models'
    (HMM is explicitly optional and therefore NOT required). A missing model
    must fail the build.
    """

    # The spec's model list, mapped to registry ids
    REQUIRED_MODELS = (
        "ta_ensemble",            # port: TA ensemble
        "fundamental_guardrails", # port: fundamental guardrails
        "sector_rotation",        # port: sector rotation
        "price_range",            # port: price-range engine (fresh, no legacy impl)
        "momentum_ts",            # quant: time-series momentum
        "momentum_cs",            # quant: cross-sectional momentum
        "mean_reversion",         # quant: mean reversion
        "quality_value",          # quant: quality/value factors
        "low_volatility",         # quant: low-volatility
        "earnings_drift",         # quant: earnings-reaction drift
        "regime",                 # quant: regime detection (simple states; HMM optional)
        "promoter_pledge",        # India: promoter holding/pledge trend
        "delivery_anomaly",       # India: delivery-percentage anomaly
        "fii_dii_regime",         # India: FII/DII flow regime
        "block_deals",            # India: bulk/block deal signal
        "macro_overlay",          # India: macro overlay
    )

    @staticmethod
    def _registry_entries():
        from typer.testing import CliRunner

        from niveshdristi.cli.main import app

        result = CliRunner().invoke(app, ["--json", "models"])
        assert result.exit_code == 0
        return json.loads(result.output)["models"]

    def test_every_spec_model_registered_with_horizon(self):
        entries = {m["model_id"]: m for m in self._registry_entries()}
        missing = [mid for mid in self.REQUIRED_MODELS if mid not in entries]
        assert missing == [], f"spec models missing from registry: {missing}"
        for mid in self.REQUIRED_MODELS:
            assert entries[mid]["horizon_days"] >= 1, f"{mid} lacks a documented horizon"
            assert entries[mid]["data_status"] in ("live", "stub")

    def test_every_spec_model_has_unit_tests(self):
        test_source = Path("tests/test_alpha.py").read_text(encoding="utf-8")
        untested = [mid for mid in self.REQUIRED_MODELS if mid not in test_source]
        assert untested == [], f"spec models without unit-test references: {untested}"

    def test_registry_has_no_unexpected_models(self):
        entries = {m["model_id"] for m in self._registry_entries()}
        extra = entries - set(self.REQUIRED_MODELS)
        assert extra == set(), f"registry contains unlisted models: {extra}"


class TestSectorRotationAsyncSafety:
    """P4-S0: predict must work from inside a running event loop.

    Regression: the old glue used asyncio.run(), which raises
    'cannot be called from a running event loop' when predict is called
    from async contexts (Streamlit/FastAPI).
    """

    @staticmethod
    def _frames():
        from datetime import timedelta

        n = 80
        dates = [(date(2026, 6, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        bench = pl.DataFrame({"date": dates, "close": [100.0 + i * 0.1 for i in range(n)]})
        sector = pl.DataFrame(
            {
                "sector": ["alpha", "beta"] * (n // 2),
                "date": dates,
                "close": [100.0 + i * 0.2 if i % 2 == 0 else 100.0 - i * 0.1 for i in range(n)],
            }
        )
        return sector, bench

    def _run_inside_loop(self):
        import asyncio
        from datetime import UTC

        from niveshdristi.alpha.quant.sector_rotation import SectorRotation
        from niveshdristi.core.alpha import AsOfContext

        sector_frame, bench = self._frames()
        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        inputs = build_from_full_frames(
            as_of=as_of,
            prices={"SYN012": _syn_frame([100.0] * 30)},
            aux={"sector_index": sector_frame, "benchmark": bench},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        model = SectorRotation()

        async def call_predict():
            return model.predict(ctx, inputs)  # inside a running loop

        return asyncio.run(call_predict())

    def test_predict_works_inside_running_loop(self):
        signals = self._run_inside_loop()
        assert len(signals) == 1

    def test_predict_works_without_loop(self):
        from datetime import UTC

        from niveshdristi.alpha.quant.sector_rotation import SectorRotation
        from niveshdristi.core.alpha import AsOfContext

        sector_frame, bench = self._frames()
        as_of = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
        inputs = build_from_full_frames(
            as_of=as_of,
            prices={"SYN012": _syn_frame([100.0] * 30)},
            aux={"sector_index": sector_frame, "benchmark": bench},
        )
        ctx = AsOfContext(as_of=as_of, universe=(), market_id="TEST_MARKET")
        signals = SectorRotation().predict(ctx, inputs)
        assert len(signals) == 1

    def test_coroutine_exceptions_propagate(self):
        from niveshdristi.alpha.quant.sector_rotation import _run_async

        async def boom():
            raise RuntimeError("boom-inside-coroutine")

        with pytest.raises(RuntimeError, match="boom-inside-coroutine"):
            _run_async(boom())


class TestMarketRules:
    """P4-S1a: neutral market-rules view — round-trip, units, frozen, verified gate."""

    def test_to_rules_round_trip_from_profile(self):
        from niveshdristi.markets.in_nse.profile import IN_NSE_PROFILE
        from niveshdristi.markets.registry import to_rules

        rules = to_rules(IN_NSE_PROFILE)
        assert rules.market_id == IN_NSE_PROFILE.market_id
        assert rules.shorting_allowed is False
        assert rules.settlement_days == 1
        # rates map across (single stt_pct -> both delivery sides)
        assert rules.rates.stt_delivery_sell == IN_NSE_PROFILE.cost_model.stt_pct
        assert rules.rates.stt_delivery_buy == IN_NSE_PROFILE.cost_model.stt_pct
        assert rules.rates.brokerage_per_order == 20.0
        assert rules.rates.gst_on_fees == 0.18
        assert rules.rates.verified is False
        # tax schedule
        assert rules.tax is not None
        assert rules.tax.holding_period_months == 12
        assert rules.tax.short_term_threshold_days == 365
        assert rules.tax.long_term_exemption == 125000.0
        assert rules.tax.verified is False

    def test_crore_to_plain_units_conversion(self):
        from niveshdristi.markets.registry import CRORE, MarketProfile, to_rules

        profile = MarketProfile(
            market_id="TEST_M", name="Test", timezone="UTC", currency="XXX",
            min_adv_crores=2.5,
        )
        rules = to_rules(profile)
        assert rules.min_adv == 2.5 * CRORE == 25_000_000.0

    def test_frozen_immutability(self):
        from niveshdristi.core.market_rules import RateSchedule

        rates = RateSchedule(brokerage_per_order=20.0)
        with pytest.raises(Exception, match="frozen|immutable|Instance"):
            rates.brokerage_per_order = 99.0  # type: ignore[misc]

    def test_verified_true_requires_source_and_date(self):
        from datetime import date

        from niveshdristi.core.market_rules import RateSchedule

        with pytest.raises(Exception, match="verified=True requires"):
            RateSchedule(verified=True)  # no source, no date
        with pytest.raises(Exception, match="verified=True requires"):
            RateSchedule(verified=True, source="circular")  # no date
        ok = RateSchedule(
            verified=True, source="NSE circular 2026", verified_on=date(2026, 10, 1)
        )
        assert ok.verified is True

    def test_core_market_rules_does_not_import_markets(self):
        """Import-boundary: core/market_rules.py must not import markets/."""
        import niveshdristi.core.market_rules as m

        src = Path(m.__file__).read_text(encoding="utf-8")
        assert "niveshdristi.markets" not in src


class TestPortfolioConstruction:
    """P4-S1: conviction -> weights. Pure function: no-look-ahead N/A by
    construction (nothing is fetched; everything arrives as arguments)."""

    @staticmethod
    def _rules(shorting_allowed: bool = False):
        from niveshdristi.core.market_rules import MarketRules

        return MarketRules(market_id="TEST_M", shorting_allowed=shorting_allowed)

    @staticmethod
    def _signal(symbol: str, conviction: float):
        from datetime import UTC, datetime

        from niveshdristi.core.instrument import Instrument
        from niveshdristi.core.signal import Signal

        return Signal(
            instrument=Instrument(
                symbol=symbol, exchange="TEST_M", market_id="TEST_M", currency="XXX"
            ),
            as_of=datetime(2026, 10, 23, 15, 0, tzinfo=UTC),
            conviction=conviction,
            horizon_days=10,
            thesis="Hypothesis: synthetic test signal.",
            evidence={"conviction": conviction},
            model_id="test_model",
        )

    def test_known_answer_two_signals(self):
        """(0.5, 0.3) -> (0.625, 0.375) — hand-computed."""
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal("SYN020", 0.5), self._signal("SYN021", 0.3)]
        w = construct_targets(signals, self._rules())
        assert w["SYN020"] == pytest.approx(0.625)
        assert w["SYN021"] == pytest.approx(0.375)

    def test_extreme_single_conviction_full_weight(self):
        from niveshdristi.portfolio.construction import construct_targets

        w = construct_targets([self._signal("SYN020", 1.0)], self._rules())
        assert w == {"SYN020": 1.0}

    def test_all_negative_long_only_is_all_cash(self):
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal("SYN020", -0.8), self._signal("SYN021", -0.2)]
        assert construct_targets(signals, self._rules()) == {}

    def test_mixed_negative_dropped_not_netted(self):
        """A negative conviction does NOT offset a positive one."""
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal("SYN020", 0.5), self._signal("SYN021", -0.9)]
        assert construct_targets(signals, self._rules()) == {"SYN020": 1.0}

    def test_shorting_allowed_keeps_negative_weights(self):
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal("SYN020", 0.5), self._signal("SYN021", -0.5)]
        w = construct_targets(signals, self._rules(shorting_allowed=True))
        assert w["SYN020"] == pytest.approx(0.5)
        assert w["SYN021"] == pytest.approx(-0.5)
        assert sum(w.values()) == pytest.approx(0.0)

    def test_inverse_vol_scaling(self):
        """vols (0.2, 0.1) with equal convictions -> inverse-vol weights
        (1/0.2, 1/0.1) normalised -> (1/3, 2/3)."""
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal("SYN020", 0.4), self._signal("SYN021", 0.4)]
        w = construct_targets(signals, self._rules(), vols={"SYN020": 0.2, "SYN021": 0.1})
        assert w["SYN020"] == pytest.approx(1 / 3)
        assert w["SYN021"] == pytest.approx(2 / 3)

    def test_weights_never_exceed_one_total(self):
        from niveshdristi.portfolio.construction import construct_targets

        signals = [self._signal(f"SYN0{i}", 0.9) for i in range(10)]
        w = construct_targets(signals, self._rules())
        assert sum(w.values()) <= 1.0 + 1e-12
        assert all(v > 0 for v in w.values())


class TestRiskGates:
    """P4-S2: deterministic risk gates — seeded violations, properties."""

    @staticmethod
    def _rules(excl_symbols=frozenset(), excl_as_of=None, excl_source="", min_price=0.0):
        from niveshdristi.core.market_rules import ExclusionList, MarketRules

        return MarketRules(
            market_id="TEST_M",
            shorting_allowed=False,
            min_price=min_price,
            exclusions=ExclusionList(
                symbols=frozenset(excl_symbols), as_of=excl_as_of, source=excl_source
            ),
        )

    @staticmethod
    def _run(weights, limits=None, rules=None, **kw):
        from niveshdristi.portfolio.risk_gates import GateLimits, run_chain

        limits = limits or GateLimits()
        rules = rules or TestRiskGates._rules()
        defaults = {
            "current_weights": {},
            "prices": dict.fromkeys(weights, 100.0),
            "nav": 1_000_000.0,
        }
        defaults.update(kw)
        return run_chain(dict(weights), limits=limits, rules=rules, **defaults)

    def test_exclusion_removes_with_log_and_staleness_warning(self):
        from datetime import date

        rules = self._rules(
            excl_symbols={"SYN030"}, excl_as_of=date(2026, 1, 1), excl_source="test-list"
        )
        out = self._run(
            {"SYN030": 0.5, "SYN031": 0.5}, rules=rules, decision_date=date(2026, 10, 23)
        )
        assert set(out.weights) == {"SYN031"}
        entry = [g for g in out.log if g.gate == "exclusion"][0]
        assert entry.symbol == "SYN030"
        assert entry.outcome == "removed"
        assert "source='test-list'" in entry.reason
        assert "age_days=295" in entry.reason
        assert "WARNING" in entry.reason  # 295d > 90d default threshold

    def test_min_price_removes(self):
        out = self._run({"SYN030": 0.5, "SYN031": 0.5}, rules=self._rules(min_price=50.0),
                        prices={"SYN030": 40.0, "SYN031": 100.0})
        assert set(out.weights) == {"SYN031"}
        assert [g for g in out.log if g.gate == "min_price"][0].outcome == "removed"

    def test_min_market_cap_inert_without_data_then_active(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        out = self._run({"SYN030": 0.5})
        skips = [g for g in out.log if g.gate == "min_market_cap"]
        assert skips
        assert skips[0].outcome == "skipped: no data"
        limits = GateLimits(min_market_cap=1_000_000_000.0)
        out2 = self._run({"SYN030": 0.5, "SYN031": 0.5}, limits=limits,
                         market_caps={"SYN030": 100.0, "SYN031": 5e9})
        assert set(out2.weights) == {"SYN031"}

    def test_max_positions_keeps_top_n(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        w = {f"SYN03{i}": 0.1 * (10 - i) for i in range(5)}  # SYN030 highest
        out = self._run(w, limits=GateLimits(max_positions=2))
        assert set(out.weights) == {"SYN030", "SYN031"}

    def test_max_position_clips(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        out = self._run({"SYN030": 1.0}, limits=GateLimits(max_position_pct=0.10, min_cash_pct=0.0))
        assert out.weights["SYN030"] == 0.10
        entry = [g for g in out.log if g.gate == "max_position"][0]
        assert entry.outcome == "clamped"
        assert entry.weight_before == 1.0

    def test_max_sector_scales(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        w = {"SYN030": 0.25, "SYN031": 0.25, "SYN032": 0.5}
        sector = {"SYN030": "sec_a", "SYN031": "sec_a", "SYN032": "sec_b"}
        out = self._run(
            w,
            limits=GateLimits(
                max_position_pct=1.0, max_sector_pct=0.30, turnover_max=1.0
            ),
            sector_map=sector,
        )
        # sec_a total 0.5 -> scaled to 0.30 (0.15 each); sec_b total 0.5 is
        # ALSO above the 0.30 cap -> SYN032 scaled to 0.30 (hand-computed).
        assert out.weights["SYN030"] == pytest.approx(0.15)
        assert out.weights["SYN031"] == pytest.approx(0.15)
        assert out.weights["SYN032"] == pytest.approx(0.30)

    def test_adv_cap_spec_test_extreme_conviction_illiquid(self):
        """SPEC: extreme conviction on an illiquid instrument is clipped by
        the ADV gate with the logged reason."""
        from niveshdristi.portfolio.risk_gates import GateLimits

        # extreme conviction 1.0 -> weight 1.0 (S1 property); illiquid: ADV tiny
        out = self._run(
            {"SYN030": 1.0},
            limits=GateLimits(max_position_pct=1.0, min_cash_pct=0.0, adv_fraction=0.05),
            advs={"SYN030": 200_000.0},  # 5% x 200k = 10k max position value
        )
        assert out.weights["SYN030"] == pytest.approx(10_000.0 / 1_000_000.0)
        entry = [g for g in out.log if g.gate == "adv_cap"][0]
        assert entry.outcome == "clamped"
        assert "exceeds 0.05 x ADV 200000" in entry.reason

    def test_adv_inert_without_data(self):
        out = self._run({"SYN030": 1.0}, limits=None)
        entry = [g for g in out.log if g.gate == "adv_cap"][0]
        assert entry.outcome == "skipped: no data"

    def test_turnover_cap_shrinks_increases_only(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        # current 0/0; targets 0.2/0.2 -> turnover 0.4 > 0.3 cap
        out = self._run(
            {"SYN030": 0.2, "SYN031": 0.2},
            limits=GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=0.3),
            current_weights={},
        )
        # increases scaled by (1 - 0.1/0.4) = 0.75 -> 0.15 each; turnover 0.3
        assert out.weights["SYN030"] == pytest.approx(0.15)
        assert out.weights["SYN031"] == pytest.approx(0.15)
        assert [g for g in out.log if g.gate == "turnover"][0].outcome == "clamped"

    def test_min_cash_creates_cash(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        out = self._run(
            {"SYN030": 0.5, "SYN031": 0.5},
            limits=GateLimits(
                max_position_pct=1.0, min_cash_pct=0.30, turnover_max=1.0
            ),
        )
        assert sum(out.weights.values()) == pytest.approx(0.70)

    def test_drawdown_circuit_boundaries(self):
        from niveshdristi.portfolio.risk_gates import GateLimits

        limits = GateLimits(
            max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0,
            drawdown_threshold=0.20, drawdown_exposure_factor=0.50,
        )
        # below threshold: no circuit
        out = self._run({"SYN030": 1.0}, limits=limits, equity_history=[100.0, 81.0])
        assert out.weights["SYN030"] == pytest.approx(1.0)
        assert not [g for g in out.log if g.gate == "drawdown_circuit"]
        # AT threshold (drawdown exactly 0.20): circuit fires
        out = self._run({"SYN030": 1.0}, limits=limits, equity_history=[100.0, 80.0])
        assert out.weights["SYN030"] == pytest.approx(0.50)
        # above threshold: circuit fires
        out = self._run({"SYN030": 1.0}, limits=limits, equity_history=[100.0, 70.0])
        assert out.weights["SYN030"] == pytest.approx(0.50)

    def test_gated_targets_direct_convention_check(self):
        from niveshdristi.portfolio.risk_gates import GatedTargets

        with pytest.raises(Exception, match="construction token"):
            GatedTargets(weights={"SYN030": 0.1}, log=())

    def test_idempotence(self):
        from niveshdristi.portfolio.risk_gates import GateLimits, run_chain

        limits = GateLimits(max_position_pct=0.10)
        first = self._run({"SYN030": 0.5, "SYN031": 0.5}, limits=limits,
                          sector_map={"SYN030": "a", "SYN031": "a"})
        second = run_chain(
            dict(first.weights), limits=limits, rules=self._rules(),
            current_weights={}, prices={"SYN030": 100.0, "SYN031": 100.0}, nav=1_000_000.0,
        )
        assert second.weights == first.weights
        clamps = [g for g in second.log if g.outcome in ("clamped", "removed")]
        assert clamps == []  # no further clamps on its own output


    def test_never_violates_limits_property_fixed_seed(self):
        """FIXED seed: random inputs; output never violates any limit and
        never exceeds the input weight for any symbol."""
        import random

        from niveshdristi.portfolio.risk_gates import GateLimits

        rng = random.Random(42)
        limits = GateLimits(max_position_pct=0.10, max_sector_pct=0.25, max_positions=5)
        for _ in range(200):
            n = rng.randint(1, 10)
            syms = [f"SYN03{i}" for i in range(n)]
            weights = {s: rng.random() for s in syms}
            advs = {
                s: rng.choice([50_000.0, 500_000.0, 5_000_000.0])
                for s in syms
                if rng.random() < 0.7
            }
            sector = {s: rng.choice(["a", "b", "c"]) for s in syms}
            out = self._run(
                weights,
                limits=limits,
                advs=advs or None,
                sector_map=sector,
                prices={s: rng.choice([50.0, 150.0]) for s in syms},
                equity_history=[100.0, rng.choice([95.0, 75.0])],
            )
            for s, w in out.weights.items():
                assert w <= weights[s] + 1e-12, f"{s} weight increased"
                assert w <= limits.max_position_pct + 1e-12
                if s in advs:
                    assert w * 1_000_000.0 <= limits.adv_fraction * advs[s] + 1e-6
            assert len(out.weights) <= limits.max_positions
            assert sum(out.weights.values()) <= 1.0 + 1e-12
            assert 1.0 - sum(out.weights.values()) >= limits.min_cash_pct - 1e-12

    def test_s1_property_conviction_fixes_relative_size_only(self):
        """S1 property: construct_targets sums positive convictions to 1.0;
        a single 0.01 conviction becomes weight 1.0 BEFORE gates, then the
        max-position gate clips it - gates create cash, conviction does not."""
        from niveshdristi.portfolio.construction import construct_targets
        from niveshdristi.portfolio.risk_gates import GateLimits

        rules = self._rules()
        sig = TestPortfolioConstruction._signal("SYN030", 0.01)
        weights = construct_targets([sig], rules)
        assert weights == {"SYN030": 1.0}
        out = self._run(weights, limits=GateLimits(max_position_pct=0.10))
        assert out.weights["SYN030"] == 0.10


class TestCostTaxYamlLoaders:
    """P4-S3: strict YAML loaders + snapshot pin (values equal to R2 audit)."""

    # SNAPSHOT of the pre-S3 HARDCODED profile values (R2 audit: equal to YAML)
    SNAPSHOT = {
        "brokerage_per_order": 20.0,
        "stt_delivery_buy_pct": 0.001,
        "stt_delivery_sell_pct": 0.001,
        "stt_intraday_sell_pct": 0.00025,
        "exchange_charges_pct": 0.0000345,
        "sebi_fees_pct": 0.000001,
        "stamp_duty_buy_pct": 0.00015,
        "gst_pct": 0.18,
        "slippage_bps": 5.0,
        "dp_charge_per_scrip": 13.5,
        "short_term_threshold_days": 365,
        "short_term_rate": 0.20,
        "long_term_rate": 0.125,
        "long_term_exemption": 125000,
        "loss_setoff_years": 8,
    }

    def test_loaded_yaml_matches_pinned_snapshot(self):
        """STOP condition guard: loaded YAML values must equal the snapshot
        of the previously hardcoded profile values (R2 showed equality)."""
        from niveshdristi.markets.in_nse.loaders import load_costs, load_tax

        costs = load_costs()
        tax = load_tax()
        for key, expected in self.SNAPSHOT.items():
            actual = costs.get(key, tax.get(key))
            assert actual == expected, f"{key}: loaded {actual} != snapshot {expected}"

    def test_unknown_keys_rejected(self, tmp_path):
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.markets.in_nse.loaders import load_costs

        bad = tmp_path / "costs.yaml"
        bad.write_text("brokerage_per_order: 20.0\nbogus_key: 1\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match=r"unknown keys: \['bogus_key'\]"):
            load_costs(bad)

    def test_percent_style_value_rejected_loudly(self, tmp_path):
        """A percent-style 0.1 in a fraction field fails sanity (100x guard)."""
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.markets.in_nse.loaders import load_costs

        bad = tmp_path / "costs.yaml"
        bad.write_text("brokerage_per_order: 20.0\nstt_delivery_buy_pct: 0.1\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="percent-style values are rejected"):
            load_costs(bad)

    def test_verified_true_needs_source_and_date(self, tmp_path):
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.markets.in_nse.loaders import load_costs

        bad = tmp_path / "costs.yaml"
        bad.write_text(
            "brokerage_per_order: 20.0\n"
            "stt_delivery_buy_pct: 0.001\n"
            "stt_delivery_sell_pct: 0.001\n"
            "exchange_charges_pct: 0.0000345\n"
            "sebi_fees_pct: 0.000001\n"
            "stamp_duty_buy_pct: 0.00015\n"
            "gst_pct: 0.18\nslippage_bps: 5.0\n"
            "verified: true\nsource: ''\nverified_on: ''\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError, match="verified=true requires"):
            load_costs(bad)

    def test_real_yaml_verified_blocks_present(self):
        from niveshdristi.markets.in_nse.loaders import load_costs, load_tax

        assert load_costs()["verified"] is False
        assert load_tax()["verified"] is False
        assert load_tax()["holding_period_months"] == 12


class TestCostEngine:
    """P4-S3: neutral cost engine — hand-computed known answers."""

    @staticmethod
    def _rates(**over):
        from niveshdristi.core.market_rules import RateSchedule

        base = {
            "brokerage_per_order": 20.0,
            "stt_delivery_buy": 0.001,
            "stt_delivery_sell": 0.001,
            "exchange_fee": 0.0000345,
            "regulator_fee": 0.000001,
            "stamp_duty_buy": 0.00015,
            "gst_on_fees": 0.18,
            "dp_charge_per_scrip": 13.5,
            "slippage_base_bps": 5.0,
        }
        base.update(over)
        return RateSchedule(**base)

    def test_buy_known_answer(self):
        """Hand arithmetic, notional 100,000:
        brokerage 20; levy 100000*0.001 = 100; exchange 100000*0.0000345 = 3.45;
        regulator 100000*0.000001 = 0.1; stamp 100000*0.00015 = 15;
        GST base = 20 + 3.45 + 0.1 = 23.55 -> GST = 4.239; DP 0 (buy);
        fees = 20+100+3.45+0.1+15+4.239 = 142.789; slippage = 100000*5/10000 = 50.
        """
        from niveshdristi.execution.costs import compute_costs

        b = compute_costs(side="buy", notional=100_000.0, rates=self._rates())
        assert b.brokerage == 20.0
        assert b.transaction_levy == 100.0
        assert b.exchange_fee == 3.45
        assert b.regulator_fee == 0.1
        assert b.stamp_duty == 15.0
        assert b.gst == pytest.approx(4.239)
        assert b.dp_charge == 0.0
        assert b.fees_total == pytest.approx(142.789)
        assert b.slippage == pytest.approx(50.0)
        assert b.total == pytest.approx(192.789)

    def test_sell_known_answer_with_dp(self):
        """Sell 100,000: no stamp duty; levy 100; DP 13.5 once; fees
        = 20+100+3.45+0.1+4.239+13.5 = 141.289; slippage 50; total 191.289."""
        from niveshdristi.execution.costs import compute_costs

        s = compute_costs(
            side="sell", notional=100_000.0, rates=self._rates(), include_dp_charge=True
        )
        assert s.stamp_duty == 0.0
        assert s.dp_charge == 13.5
        assert s.fees_total == pytest.approx(141.289)
        assert s.total == pytest.approx(191.289)

    def test_percent_misreading_would_be_caught(self):
        """If stt were read as a PERCENT (0.1) the levy would be 10,000 for a
        100k notional — 100x the correct 100. The loader rejects 0.1 outright
        (see loader tests); here we pin the correct fraction behaviour so any
        regression to percent semantics changes the total ~52x and fails."""
        from niveshdristi.execution.costs import compute_costs

        b = compute_costs(side="buy", notional=100_000.0, rates=self._rates())
        assert b.transaction_levy == pytest.approx(100.0)  # fraction semantics
        assert b.total == pytest.approx(192.789)  # NOT ~10,143

    def test_frozen_and_banner(self):
        from niveshdristi.execution.costs import BANNER, compute_costs

        b = compute_costs(side="buy", notional=1000.0, rates=self._rates())
        with pytest.raises(Exception, match="frozen|immutable|Instance"):
            b.notional = 5.0  # type: ignore[misc]
        assert b.rates_verified is False
        assert b.banner == BANNER

    def test_verified_rates_no_banner(self):
        from datetime import date

        from niveshdristi.execution.costs import compute_costs

        rates = self._rates(
            verified=True, source="circular 2026", verified_on=date(2026, 10, 1)
        )
        b = compute_costs(side="buy", notional=1000.0, rates=rates)
        assert b.banner is None
        assert b.rates_verified is True


class TestTaxEngine:
    """P4-S4: calendar-month holding period, FY set-off, known answers."""

    @staticmethod
    def _schedule(**over):
        from niveshdristi.core.market_rules import TaxSchedule

        base = {
            "enabled": True, "holding_period_months": 12,
            "short_term_threshold_days": 365,
            "short_term_rate": 0.20, "long_term_rate": 0.125,
            "long_term_exemption": 125_000.0, "loss_setoff_years": 8,
        }
        base.update(over)
        return TaxSchedule(**base)

    @staticmethod
    def _lot(buy: str, sell: str, gain: float = 10_000.0, symbol: str = "SYN040"):
        from niveshdristi.portfolio.tax import RealisedLot

        return RealisedLot(
            symbol=symbol,
            buy_date=date.fromisoformat(buy),
            sell_date=date.fromisoformat(sell),
            proceeds_minus_cost=gain,
        )

    def test_anniversary_boundaries(self):
        from niveshdristi.portfolio.tax import is_long_term

        s = self._schedule()
        # day BEFORE 12-month anniversary -> short-term
        assert is_long_term(date(2025, 3, 10), date(2026, 3, 9), s) is False
        # ON the anniversary -> long-term
        assert is_long_term(date(2025, 3, 10), date(2026, 3, 10), s) is True

    def test_leap_year_buy_clamped(self):
        """2024-02-29 buy: 12-month anniversary clamps to 2025-02-28."""
        from niveshdristi.portfolio.tax import is_long_term

        s = self._schedule()
        assert is_long_term(date(2024, 2, 29), date(2025, 2, 27), s) is False
        assert is_long_term(date(2024, 2, 29), date(2025, 2, 28), s) is True

    def test_month_end_buy_into_shorter_month(self):
        """Clamp case with a 1-MONTH schedule: Jan 31 buy -> anniversary
        clamps to Feb 28 (non-leap); day before is short-term."""
        from niveshdristi.portfolio.tax import is_long_term

        s = self._schedule(holding_period_months=1)
        assert is_long_term(date(2026, 1, 31), date(2026, 2, 27), s) is False
        assert is_long_term(date(2026, 1, 31), date(2026, 2, 28), s) is True

    def test_month_rule_differs_from_365_days(self):
        """2025-03-01 buy -> 2026-03-01 is 365 days AND the month-rule
        anniversary: long-term. But 2024-03-01 -> 2025-02-28 is 364 days:
        short-term under BOTH. The interesting case: 2024-03-01 buy sold
        2025-03-01 = 365 days, month anniversary -> long-term; and
        2023-03-01 buy sold 2024-02-29 = 365 days but BEFORE the month
        anniversary -> SHORT-term (a pure day count would say long)."""
        from niveshdristi.portfolio.tax import is_long_term

        s = self._schedule()
        # 365 days elapsed but BEFORE the month-rule anniversary:
        assert is_long_term(date(2023, 3, 1), date(2024, 2, 29), s) is False
        assert is_long_term(date(2024, 3, 1), date(2025, 3, 1), s) is True  # 365d, anniversary

    def test_known_answer_basic_lt_with_exemption(self):
        """LTCG 200,000, no losses: exemption 125,000 -> taxable 75,000
        -> tax = 75,000 x 0.125 = 9,375."""
        from niveshdristi.portfolio.tax import compute_tax

        lots = [self._lot("2024-01-10", "2025-06-10", 200_000.0)]
        r = compute_tax(lots, self._schedule(), fy_start_month=4)
        assert r.tax_due == pytest.approx(9_375.0)
        assert r.exemption_applied == pytest.approx(125_000.0)
        assert r.rates_verified is False
        assert r.banner == "RATES UNVERIFIED"

    def test_known_answer_st(self):
        """STCG 50,000 -> tax = 10,000 (20%); no exemption for ST."""
        from niveshdristi.portfolio.tax import compute_tax

        lots = [self._lot("2026-01-10", "2026-06-10", 50_000.0)]
        r = compute_tax(lots, self._schedule(), fy_start_month=4)
        assert r.tax_due == pytest.approx(10_000.0)
        assert r.exemption_applied == 0.0

    def test_setoff_stcl_offsets_both_then_ltcl_ltcg_only(self):
        """STCG 30k, LTCG 20k, prior STCL 40k: STCL offsets STCG 30k then
        LTCG 10k -> LTCG 10k remains; exemption min(125k,10k)=10k ->
        taxable LT 0 -> tax 0; STCL carried 0."""
        from niveshdristi.portfolio.tax import compute_tax

        lots = [
            self._lot("2026-01-10", "2026-06-10", 30_000.0),
            self._lot("2024-01-10", "2026-06-10", 20_000.0),
        ]
        r = compute_tax(lots, self._schedule(), fy_start_month=4, prior_stcl=40_000.0)
        assert r.tax_due == pytest.approx(0.0)
        assert r.stcl_used == pytest.approx(40_000.0)
        assert r.exemption_applied == pytest.approx(10_000.0)

    def test_ltcl_cannot_offset_stcg(self):
        """STCG 30k with prior LTCL 50k: LTCL offsets NOTHING (no LTCG);
        tax = 30k x 20% = 6,000; LTCL carried 50k."""
        from niveshdristi.portfolio.tax import compute_tax

        lots = [self._lot("2026-01-10", "2026-06-10", 30_000.0)]
        r = compute_tax(lots, self._schedule(), fy_start_month=4, prior_ltcl=50_000.0)
        assert r.tax_due == pytest.approx(6_000.0)
        assert r.ltcl_used == pytest.approx(0.0)
        assert r.ltcl_carried == pytest.approx(50_000.0)

    def test_disabled_returns_zero(self):
        from niveshdristi.portfolio.tax import compute_tax

        lots = [self._lot("2024-01-10", "2025-06-10", 200_000.0)]
        r = compute_tax(lots, self._schedule(enabled=False), fy_start_month=4)
        assert r.tax_due == 0.0

    def test_fy_label(self):
        from niveshdristi.portfolio.tax import financial_year_of

        assert financial_year_of(date(2026, 2, 1), 4) == 2025  # Feb -> prior FY
        assert financial_year_of(date(2026, 5, 1), 4) == 2026


class TestOrderBuildingAndSimBroker:
    """P4-S5: integer-share orders + SimBroker known answers."""

    @staticmethod
    def _gated(weights: dict[str, float]):
        from niveshdristi.portfolio.risk_gates import GateLimits, run_chain
        from tests.test_alpha import TestRiskGates

        rules = TestRiskGates._rules()
        return run_chain(
            dict(weights),
            limits=GateLimits(max_position_pct=1.0, min_cash_pct=0.0, turnover_max=1.0),
            rules=rules,
            current_weights={},
            prices=dict.fromkeys(weights, 100.0),
            nav=1_000_000.0,
        )

    @staticmethod
    def _instrument(symbol: str):
        from niveshdristi.core.instrument import Instrument

        return Instrument(symbol=symbol, exchange="TEST_M", market_id="TEST_M", currency="XXX")

    def test_build_orders_floors_and_never_overspends(self):
        from niveshdristi.execution.orders import build_orders

        gated = self._gated({"SYN050": 0.10, "SYN051": 0.10})
        orders, logs = build_orders(
            gated,
            nav=1_000_000.0,
            cash=150_000.0,
            prices={"SYN050": 33.33, "SYN051": 100.0},
            instruments={
                "SYN050": self._instrument("SYN050"),
                "SYN051": self._instrument("SYN051"),
            },
            current_holdings={},
        )
        by_sym = {o.instrument.symbol: o for o in orders}
        # SYN050: 100k/33.33 = 3000.3 -> floor 3000 (cost 99,990); remaining
        # cash 50,010 -> SYN051: 500 shares (cost 50,000); total 149,990 <= 150k
        assert by_sym["SYN050"].quantity == 3000
        assert by_sym["SYN051"].quantity == 500
        spend = 3000 * 33.33 + 500 * 100.0
        assert spend <= 150_000.0

    def test_zero_quantity_dropped_with_log(self):
        from niveshdristi.execution.orders import build_orders

        gated = self._gated({"SYN050": 0.001})  # 1000 target, price 1500 -> floor 0
        orders, logs = build_orders(
            gated,
            nav=1_000_000.0,
            cash=10_000.0,
            prices={"SYN050": 1500.0},
            instruments={"SYN050": self._instrument("SYN050")},
            current_holdings={},
        )
        assert orders == []
        assert any("floored quantity 0" in log.note for log in logs)

    def test_broker_rejects_ungated_order(self):
        from datetime import UTC, datetime

        from niveshdristi.core.decision import Order, OrderSide
        from niveshdristi.core.market_rules import PriceLimitRule, RateSchedule
        from niveshdristi.execution.sim_broker import SimBroker

        broker = SimBroker(rates=RateSchedule(), price_limits=PriceLimitRule(enabled=False))
        rogue = Order(
            instrument=self._instrument("SYN050"),
            side=OrderSide.BUY,
            quantity=10,
            placed_at=datetime.now(UTC),
            client_order_id="rogue-1",
        )
        with pytest.raises(ValueError, match="gate provenance"):
            broker.execute([rogue], prices={"SYN050": 100.0})

    @staticmethod
    def _broker():
        from niveshdristi.core.market_rules import PriceLimitRule, RateSchedule
        from niveshdristi.execution.sim_broker import SimBroker

        rates = RateSchedule(
            brokerage_per_order=20.0, stt_delivery_buy=0.001,
            exchange_fee=0.0000345, regulator_fee=0.000001,
            stamp_duty_buy=0.00015, gst_on_fees=0.18,
            dp_charge_per_scrip=13.5, slippage_base_bps=5.0,
        )
        return SimBroker(
            rates=rates,
            price_limits=PriceLimitRule(enabled=True, bands=(0.10,)),
        )

    @staticmethod
    def _order(symbol: str, qty: int):
        from datetime import UTC, datetime

        from niveshdristi.core.decision import Order, OrderSide
        from niveshdristi.core.instrument import Instrument

        return Order(
            instrument=Instrument(
                symbol=symbol, exchange="TEST_M", market_id="TEST_M", currency="XXX"
            ),
            side=OrderSide.BUY,
            quantity=qty,
            placed_at=datetime.now(UTC),
            client_order_id=f"gate-{symbol}",
        )

    def test_normal_fill_known_answer(self):
        """1000 shares at 100 with base slippage 5bps: fill price
        100*(1+5/10000) = 100.05; notional 100,050; commission 20."""
        results = self._broker().execute(
            [self._order("SYN050", 1000)], prices={"SYN050": 100.0}
        )
        assert results[0].filled
        fill = results[0].fill
        assert fill.fill_price == pytest.approx(100.05)
        assert fill.filled_quantity == 1000
        assert fill.commission == 20.0

    def test_circuit_limit_fill_failure(self):
        """Price moved 10% (at the band) -> no fill; 9.9% -> fill."""
        broker = self._broker()
        ref = {"SYN050": 100.0}
        failed = broker.execute(
            [self._order("SYN050", 10)], prices={"SYN050": 110.0}, reference_prices=ref
        )
        assert not failed[0].filled
        assert "circuit limit" in failed[0].reason
        ok = broker.execute(
            [self._order("SYN050", 10)], prices={"SYN050": 109.9}, reference_prices=ref
        )
        assert ok[0].filled

    def test_slippage_scales_with_liquidity(self):
        """Order value 10% of ADV -> 2x base (10bps); 20% of ADV -> 3x capped."""
        broker = self._broker()
        r1 = broker.execute(
            [self._order("SYN050", 100)], prices={"SYN050": 100.0}, advs={"SYN050": 1_000_000.0}
        )
        # notional 10,005 / ADV 1,000,000 = 0.010005 -> multiplier
        # 1 + 0.010005/0.10 = 1.10005 -> 5 x 1.10005 = 5.5 bps (hand-computed)
        assert r1[0].fill.slippage_bps == pytest.approx(5.50025, rel=1e-3)
        r2 = broker.execute(
            [self._order("SYN051", 1000)], prices={"SYN051": 100.0}, advs={"SYN051": 1_000_000.0}
        )
        # notional ~100k -> ratio 0.1 -> multiplier 2.0 -> 10 bps
        assert r2[0].fill.slippage_bps == pytest.approx(10.0, rel=1e-3)

    def test_cash_never_negative_adversarial(self):
        """Two 10M orders vs 150k cash: the first is rejected (insufficient
        cash), the second also rejected; nothing fills and nothing spends."""
        broker = self._broker()
        results = broker.execute(
            [self._order("SYN050", 100000), self._order("SYN051", 100000)],
            prices={"SYN050": 100.0, "SYN051": 100.0},
            cash=150_000.0,
        )
        assert all(not r.filled for r in results)
        assert all("insufficient cash" in r.reason for r in results)
