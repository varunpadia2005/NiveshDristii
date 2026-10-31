"""
Test core types: Instrument, Decision, Order, Fill, SessionRecord, AlphaModel.

Protects the rule that all core types are frozen Pydantic v2 models
that reject missing required fields, and that AlphaModel protocol is satisfied.
"""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from niveshdristi.core import (
    AlphaModel,
    Decision,
    Fill,
    Instrument,
    Order,
    PositionSnapshot,
    SessionRecord,
    Signal,
)


class TestInstrument:
    """Instrument is frozen and rejects missing required fields."""

    def test_accepts_complete_instrument(self):
        """Complete instrument is valid."""
        inst = Instrument(
            symbol="RELIANCE",
            exchange="NSE",
            market_id="IN_NSE",
            currency="INR",
        )
        assert inst.symbol == "RELIANCE"
        assert inst.exchange == "NSE"

    def test_rejects_missing_symbol(self):
        """Missing symbol raises ValidationError with missing error."""
        with pytest.raises(ValidationError) as exc_info:
            Instrument(exchange="NSE", market_id="IN_NSE", currency="INR")
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("symbol",) for e in errors)

    def test_rejects_missing_exchange(self):
        """Missing exchange raises ValidationError with missing error."""
        with pytest.raises(ValidationError) as exc_info:
            Instrument(symbol="RELIANCE", market_id="IN_NSE", currency="INR")
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("exchange",) for e in errors)

    def test_rejects_missing_market_id(self):
        """Missing market_id raises ValidationError with missing error."""
        with pytest.raises(ValidationError) as exc_info:
            Instrument(symbol="RELIANCE", exchange="NSE", currency="INR")
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("market_id",) for e in errors)

    def test_rejects_missing_currency(self):
        """Missing currency raises ValidationError with missing error."""
        with pytest.raises(ValidationError) as exc_info:
            Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE")
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("currency",) for e in errors)

    def test_frozen_assignment_raises(self):
        """Instrument is frozen - assignment raises ValidationError with frozen_instance."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            inst.symbol = "TCS"
        errors = exc_info.value.errors()
        assert any(e["type"] == "frozen_instance" and e["loc"] == ("symbol",) for e in errors)


class TestDecision:
    """Decision is frozen and validates delta_shares -> side mapping."""

    def test_accepts_valid_decision(self):
        """Valid decision with all fields."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        d = Decision(
            instrument=inst,
            target_weight=0.05,
            target_shares=100,
            current_shares=50,
            delta_shares=50,
            side=None,  # will be set to BUY
            reason="test",
        )
        assert d.side is not None  # auto-set from delta_shares
        assert d.delta_shares == 50

    def test_delta_shares_zero_sets_side_none(self):
        """delta_shares=0 forces side=None."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        d = Decision(
            instrument=inst,
            target_weight=0.05,
            target_shares=100,
            current_shares=100,
            delta_shares=0,
            side=None,
            reason="test",
        )
        assert d.side is None

    def test_frozen_assignment_raises(self):
        """Decision is frozen."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        d = Decision(
            instrument=inst,
            target_weight=0.05,
            target_shares=100,
            current_shares=50,
            delta_shares=50,
            side=None,
            reason="test",
        )
        with pytest.raises(ValidationError) as exc_info:
            d.target_weight = 0.1
        errors = exc_info.value.errors()
        assert any(e["type"]
            == "frozen_instance" and e["loc"] == ("target_weight",) for e in errors)


class TestOrder:
    """Order validates quantity, limit_price for LIMIT orders."""

    def test_accepts_market_order(self):
        """Market order without limit_price is valid."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        o = Order(instrument=inst, side="buy", quantity=100)
        assert o.order_type == "market"
        assert o.limit_price is None

    def test_accepts_limit_order_with_price(self):
        """Limit order with limit_price is valid."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        o = Order(
            instrument=inst,
            side="buy",
            quantity=100,
            order_type="limit",
            limit_price=2500.0,
        )
        assert o.order_type == "limit"
        assert o.limit_price == 2500.0

    def test_rejects_limit_order_without_price(self):
        """Limit order without limit_price raises ValidationError."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Order(
                instrument=inst,
                side="buy",
                quantity=100,
                order_type="limit",
                # limit_price missing
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "value_error" and "limit_price" in str(e["msg"]) for e in errors)

    def test_rejects_zero_quantity(self):
        """Quantity <= 0 raises ValidationError with greater_than error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        with pytest.raises(ValidationError) as exc_info:
            Order(instrument=inst, side="buy", quantity=0)
        errors = exc_info.value.errors()
        assert any(e["type"] == "greater_than" and e["loc"] == ("quantity",) for e in errors)


class TestFill:
    """Fill validates filled_quantity, fill_price, commission, fees."""

    def test_accepts_valid_fill(self):
        """Valid fill with all fields."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        o = Order(instrument=inst, side="buy", quantity=100)
        f = Fill(
            order=o,
            filled_quantity=100,
            fill_price=2500.0,
            fill_time=datetime.now(UTC),
            commission=20.0,
            fees=5.0,
        )
        assert f.total_cost == 25.0
        assert f.notional == 250000.0

    def test_rejects_filled_quantity_exceeds_order(self):
        """filled_quantity > order.quantity raises ValidationError."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        o = Order(instrument=inst, side="buy", quantity=50)
        with pytest.raises(ValidationError) as exc_info:
            Fill(
                order=o,
                filled_quantity=100,  # exceeds 50
                fill_price=2500.0,
                fill_time=datetime.now(UTC),
            )
        errors = exc_info.value.errors()
        wanted = "filled_quantity cannot exceed order.quantity"
        assert any(
            e["type"] == "value_error" and wanted in str(e["msg"]) for e in errors
        )

    def test_rejects_negative_commission(self):
        """Negative commission raises ValidationError with greater_than_equal error."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        o = Order(instrument=inst, side="buy", quantity=100)
        with pytest.raises(ValidationError) as exc_info:
            Fill(
                order=o,
                filled_quantity=100,
                fill_price=2500.0,
                fill_time=datetime.now(UTC),
                commission=-1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["type"]
            == "greater_than_equal" and e["loc"] == ("commission",) for e in errors)


class TestSessionRecord:
    """SessionRecord is frozen, computes hash, verifies chain."""

    def test_genesis_record_creation(self):
        """Genesis record has previous_hash = '0'*64."""
        snap = PositionSnapshot(
            instrument=Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE",
                currency="INR"),
            shares=100,
            avg_cost=2500.0,
            market_value=250000.0,
        )
        rec = SessionRecord.create_genesis_record(
            initial_cash=1_000_000,
            session_date=date(2024, 1, 1),
            initial_positions=(snap,),
        )
        assert rec.session_id == 0
        assert rec.previous_hash == "0" * 64
        assert rec.cash_after == 1_000_000

    def test_compute_hash_deterministic(self):
        """compute_hash is deterministic."""
        snap = PositionSnapshot(
            instrument=Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE",
                currency="INR"),
            shares=100,
            avg_cost=2500.0,
            market_value=250000.0,
        )
        rec = SessionRecord.create_genesis_record(
            initial_cash=1_000_000,
            session_date=date(2024, 1, 1),
            initial_positions=(snap,),
        )
        h1 = rec.compute_hash()
        h2 = rec.compute_hash()
        assert h1 == h2

    def test_verify_chain(self):
        """verify_chain checks link to previous record."""
        snap = PositionSnapshot(
            instrument=Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE",
                currency="INR"),
            shares=100,
            avg_cost=2500.0,
            market_value=250000.0,
        )
        rec0 = SessionRecord.create_genesis_record(
            initial_cash=1_000_000,
            session_date=date(2024, 1, 1),
            initial_positions=(snap,),
        )
        rec1 = SessionRecord(
            session_id=1,
            session_date=date(2024, 1, 2),
            previous_hash=rec0.compute_hash(),
            cash_after=1_000_000,
            equity_after=1_000_000,
        )
        assert rec1.verify_chain(rec0)
        assert not rec1.verify_chain(None)


class TestAlphaModelProtocol:
    """AlphaModel protocol is satisfied by a stub implementation."""

    def test_stub_model_satisfies_protocol(self):
        """A class implementing predict and registry_entry satisfies AlphaModel protocol."""
        from niveshdristi.core.alpha import AsOfContext

        class StubModel:
            model_id = "stub_model"

            def predict(self, ctx: AsOfContext) -> list:
                return []

            def registry_entry(self):
                from niveshdristi.core.alpha import ModelRegistryEntry
                return ModelRegistryEntry(
                    model_id=self.model_id,
                    horizon_days=10,
                    required_data=("prices",),
                    pit_safe=True,
                    data_status="stub",
                    description="Stub for testing",
                )

        stub = StubModel()
        # Runtime checkable protocol
        assert isinstance(stub, AlphaModel)
        # Can call predict
        ctx = AsOfContext(
            as_of=datetime.now(UTC),
            universe=(),
            market_id="IN_NSE",
        )
        signals = stub.predict(ctx)
        assert isinstance(signals, list)

    def test_protocol_rejects_missing_methods(self):
        """Class missing required methods fails isinstance check."""

        class IncompleteModel:
            model_id = "incomplete"
            # missing predict and registry_entry

        incomplete = IncompleteModel()
        # Protocol is runtime_checkable, so missing methods should fail
        assert not isinstance(incomplete, AlphaModel)


class TestSignalConvictionEdgeCases:
    """Signal conviction edge cases already covered in test_core_signal.py,
    but verify Instrument integration here."""

    def test_signal_with_instrument(self):
        """Signal with Instrument object works."""
        inst = Instrument(symbol="RELIANCE", exchange="NSE", market_id="IN_NSE", currency="INR")
        s = Signal(
            instrument=inst,
            as_of=datetime.now(UTC),
            conviction=0.5,
            horizon_days=10,
            thesis="Test thesis",
            model_id="test_model",
        )
        assert s.instrument.symbol == "RELIANCE"
        assert s.instrument.market_id == "IN_NSE"

class TestAlphaModelSeamProtocol:
    """ADDED in P3-S1: the (ctx, inputs) predict signature. Additive only —
    the older one-argument stub above still satisfies the runtime protocol
    check because runtime_checkable verifies method presence, not signatures."""

    def test_model_with_inputs_signature_satisfies_protocol(self):
        """A predict(ctx, inputs) implementation satisfies AlphaModel."""

        from niveshdristi.core.alpha import AsOfContext, ModelRegistryEntry
        from niveshdristi.marketdata.context import build_model_inputs

        class SeamModel:
            model_id = "seam_model"

            def predict(self, ctx, inputs):
                assert inputs.as_of <= ctx.as_of.date()
                return []

            def registry_entry(self):
                return ModelRegistryEntry(
                    model_id=self.model_id,
                    horizon_days=5,
                    required_data=("prices",),
                    pit_safe=True,
                    data_status="live",
                    description="Seam conformance stub",
                )

        model = SeamModel()
        assert isinstance(model, AlphaModel)
        ctx = AsOfContext(
            as_of=datetime.now(UTC),
            universe=(),
            market_id="IN_NSE",
        )
        inputs = build_model_inputs(as_of=ctx.as_of, prices={})
        assert model.predict(ctx, inputs) == []
