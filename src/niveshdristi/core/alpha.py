"""AlphaModel protocol — the contract for all signal generators."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal


@dataclass(frozen=True, slots=True)
class AsOfContext:
    """
    Context passed to AlphaModel.predict() containing point-in-time data.

    Attributes:
        as_of: The simulation timestamp — only data available at or before this
               time may be used to generate signals.
        universe: List of instruments available for signal generation at this time.
        market_id: Market identifier (e.g., "IN_NSE") for market-specific logic.
    """

    as_of: datetime
    universe: tuple[Instrument, ...]
    market_id: str


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    """
    Metadata for a registered AlphaModel.

    Attributes:
        model_id: Unique identifier
        horizon_days: Default signal horizon
        required_data: List of data types needed (e.g., "prices", "fundamentals", "corporate_actions")
        pit_safe: True if model guarantees point-in-time safety (no look-ahead)
        data_status: "live" | "stub" | "unavailable" — for models awaiting data sources
        description: Human-readable description of the model's approach
    """

    model_id: str
    horizon_days: int
    required_data: tuple[str, ...]
    pit_safe: bool
    data_status: str = "live"
    description: str = ""


@runtime_checkable
class AlphaModel(Protocol):
    """
    Protocol for all alpha models (quant, fundamental, LLM-based, etc.).

    Every model must implement:
    - `model_id`: Unique identifier
    - `predict(ctx) -> list[Signal]`: Generate signals for the given context
    - `registry_entry() -> ModelRegistryEntry`: Metadata for registry/discovery
    """

    @property
    def model_id(self) -> str:
        """Unique identifier for this model (e.g., 'ta_ensemble', 'momentum_cs', 'promoter_pledge')."""
        ...

    def predict(self, ctx: AsOfContext) -> list[Signal]:
        """
        Generate signals for the given point-in-time context.

        Args:
            ctx: Contains as_of timestamp, universe, and market_id.

        Returns:
            List of Signals. Empty list = no opinion.
        """
        ...

    def registry_entry(self) -> ModelRegistryEntry:
        """Return metadata for the model registry."""
        ...