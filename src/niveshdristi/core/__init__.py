"""Core domain types — market-agnostic, Pydantic v2 frozen models."""

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelRegistryEntry
from niveshdristi.core.decision import Decision, Fill, Order, OrderSide, OrderType
from niveshdristi.core.errors import (
    ConfigurationError,
    DataError,
    ExecutionError,
    NiveshDristiError,
    ValidationError,
)
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.session import PositionSnapshot, SessionRecord, create_genesis_record
from niveshdristi.core.signal import Signal

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
