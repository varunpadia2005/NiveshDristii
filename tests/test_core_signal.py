"""
Test core Signal type constraints.

Protects the rule that Signal.conviction must be in [-1, +1] and that
required fields (horizon_days, thesis, as_of, model_id) are enforced.
Signals are frozen Pydantic models - assignment to fields must raise ValidationError.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from niveshdristi.core import Signal, Instrument


class TestSignalConvictionBounds:
    """Signal.conviction must be clamped to [-1, +1]."""

    def test_accepts_conviction_1(self):
        """Upper bound +1 is valid."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        s = Signal(
            instrument=inst,
            as_of=datetime.now(timezone.utc),
            conviction=1.0,
            horizon_days=10,
            thesis="Strong bullish",
            model_id="test_model",
        )
        assert s.conviction == 1.0

    def test_accepts_conviction_0(self):
        """Neutral 0 is valid."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        s = Signal(
            instrument=inst,
            as_of=datetime.now(timezone.utc),
            conviction=0.0,
            horizon_days=10,
            thesis="Neutral",
            model_id="test_model",
        )
        assert s.conviction == 0.0

    def test_accepts_conviction_neg1(self):
        """Lower bound -1 is valid."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        s = Signal(
            instrument=inst,
            as_of=datetime.now(timezone.utc),
            conviction=-1.0,
            horizon_days=10,
            thesis="Bearish",
            model_id="test_model",
        )
        assert s.conviction == -1.0

    def test_rejects_conviction_above_1(self):
        """+1.01 must raise ValidationError with less_than_equal error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                as_of=datetime.now(timezone.utc),
                conviction=1.01,
                horizon_days=10,
                thesis="Too bullish",
                model_id="test_model",
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "less_than_equal" and e["loc"] == ("conviction",) for e in errors)

    def test_rejects_conviction_below_neg1(self):
        """-1.01 must raise ValidationError with greater_than_equal error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                as_of=datetime.now(timezone.utc),
                conviction=-1.01,
                horizon_days=10,
                thesis="Too bearish",
                model_id="test_model",
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "greater_than_equal" and e["loc"] == ("conviction",) for e in errors)


class TestSignalRequiredFields:
    """Signal requires horizon_days, thesis, as_of, model_id."""

    def test_requires_horizon_days(self):
        """Missing horizon_days must raise ValidationError with missing error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                as_of=datetime.now(timezone.utc),
                conviction=0.5,
                thesis="Test",
                model_id="test_model",
                # horizon_days missing
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("horizon_days",) for e in errors)

    def test_requires_thesis(self):
        """Empty thesis must raise ValidationError with value_error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                as_of=datetime.now(timezone.utc),
                conviction=0.5,
                horizon_days=10,
                thesis="",  # empty
                model_id="test_model",
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "value_error" and e["loc"] == ("thesis",) for e in errors)

    def test_requires_as_of(self):
        """Missing as_of must raise ValidationError with missing error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                conviction=0.5,
                horizon_days=10,
                thesis="Test",
                model_id="test_model",
                # as_of missing
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("as_of",) for e in errors)

    def test_requires_model_id(self):
        """Empty model_id must raise ValidationError with value_error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Signal(
                instrument=inst,
                as_of=datetime.now(timezone.utc),
                conviction=0.5,
                horizon_days=10,
                thesis="Test",
                model_id="",  # empty
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "value_error" and e["loc"] == ("model_id",) for e in errors)


class TestSignalFrozen:
    """Signal is frozen - field assignment must raise ValidationError with frozen_instance."""

    def test_frozen_assignment_raises(self):
        """Assignment to any field must raise ValidationError with frozen_instance."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        s = Signal(
            instrument=inst,
            as_of=datetime.now(timezone.utc),
            conviction=0.5,
            horizon_days=10,
            thesis="Test",
            model_id="test_model",
        )
        with pytest.raises(ValidationError) as exc_info:
            s.conviction = 0.9
        errors = exc_info.value.errors()
        assert any(e["type"] == "frozen_instance" and e["loc"] == ("conviction",) for e in errors)