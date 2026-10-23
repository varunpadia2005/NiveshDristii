"""
Test the alpha seam: ModelInputs read-only semantics, the validating builder,
the no-look-ahead property test (with a deliberately leaky CANARY), and the
import boundary (core/, marketdata/, alpha/ must not import niveshdristi.markets).

All frames here are SYNTHETIC and generated in code (neutral names SYN001...).
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
    n = len(closes)
    dates = [(start + __import__("datetime").timedelta(days=i)).isoformat() for i in range(n)]
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
