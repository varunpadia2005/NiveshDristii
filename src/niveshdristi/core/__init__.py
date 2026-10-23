"""Core domain types — market-agnostic, Pydantic v2 frozen models."""

from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal
from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelRegistryEntry
from niveshdristi.core.decision import Decision, Order, Fill, OrderSide, OrderType
from niveshdristi.core.session import SessionRecord, PositionSnapshot, create_genesis_record
from niveshdristi.core.errors import (
    NiveshDristiError,
    DataError,
    ValidationError,
    ExecutionError,
    ConfigurationError,
)

__all__ = [
    "Instrument",
    "Signal",
    "AlphaModel",
    "AsOfContext",
    "ModelRegistryEntry",
    "Decision",
    "Order",
    "Fill",
    "OrderSide",
    "OrderType",
    "SessionRecord",
    "PositionSnapshot",
    "create_genesis_record",
    "NiveshDristiError",
    "DataError",
    "ValidationError",
    "ExecutionError",
    "ConfigurationError",
]