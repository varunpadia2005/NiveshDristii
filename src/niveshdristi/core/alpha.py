"""AlphaModel protocol — the contract for all signal generators."""

from __future__ import annotations

from datetime import date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

if TYPE_CHECKING:  # polars is annotation-only here: core has no runtime polars dependency
    import polars as pl


class AsOfContext(BaseModel):
    """
    Context passed to AlphaModel.predict() containing point-in-time data.

    Attributes:
        as_of: The simulation timestamp — only data available at or before this
               time may be used to generate signals.
        universe: List of instruments available for signal generation at this time.
        market_id: Market identifier (e.g., "IN_NSE") for market-specific logic.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: datetime
    universe: tuple[Instrument, ...]
    market_id: str


class ModelRegistryEntry(BaseModel):
    """
    Metadata for a registered AlphaModel.

    Attributes:
        model_id: Unique identifier
        horizon_days: Default signal horizon
        required_data: List of data types needed (e.g., "prices", "fundamentals",
            "corporate_actions")
        pit_safe: True if model guarantees point-in-time safety (no look-ahead)
        data_status: "live" | "stub" | "unavailable" — for models awaiting data sources
        description: Human-readable description of the model's approach
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(..., min_length=1)
    horizon_days: int = Field(..., ge=1)
    required_data: tuple[str, ...] = ()
    pit_safe: bool = True
    data_status: str = Field(default="live", pattern="^(live|stub|unavailable)$")
    description: str = ""


@runtime_checkable
class AlphaModel(Protocol):
    """
    Protocol for all alpha models (quant, fundamental, LLM-based, etc.).

    Every model must implement:
    - `model_id`: Unique identifier
    - `predict(ctx, inputs) -> list[Signal]`: Generate signals for the given
      context, using ONLY the data in `inputs` (which is validated to contain
      nothing dated after ctx.as_of / inputs.as_of)
    - `registry_entry() -> ModelRegistryEntry`: Metadata for registry/discovery
    """

    @property
    def model_id(self) -> str:
        """Unique identifier for this model (e.g., 'ta_ensemble',
        'momentum_cs', 'promoter_pledge')."""
        ...

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        """
        Generate signals for this point-in-time context.

        Args:
            ctx: Contains as_of timestamp, universe, and market_id.
            inputs: Read-only data bundle; no row dated after inputs.as_of
                may be used (the builder enforces this invariant).

        Returns:
            List of Signals. Empty list = no opinion.
        """
        ...

    def registry_entry(self) -> ModelRegistryEntry:
        """Return metadata for the model registry."""
        ...


class ModelInputs:
    """Read-only data bundle handed to AlphaModel.predict.

    Deliberately a PLAIN class: dataclass decorators are banned in core/ and
    this is not a Pydantic model (frames are arbitrary types, and arbitrary
    type permissions are banned in core models). polars appears only under
    TYPE_CHECKING, so core/ has no runtime dependency on it.

    Read-only is SHALLOW: attribute rebinding is blocked (private __slots__,
    no setters) and the mappings are wrapped in MappingProxyType, so a model
    cannot add/replace/rebind series. The polars DataFrames themselves are
    NOT deep-frozen — a model holding a frame reference could still build a
    mutated copy, exactly like any function it calls could. Point-in-time
    safety therefore rests on the builder's construction-time validation
    (see marketdata.context.build_model_inputs), not on deep immutability.

    Built via marketdata.context.build_model_inputs / build_from_full_frames.
    """

    __slots__ = ("_as_of", "_prices", "_fundamentals", "_aux")

    if TYPE_CHECKING:
        # Declared for the type checker only; values set via object.__setattr__
        _as_of: date
        _prices: MappingProxyType
        _fundamentals: MappingProxyType
        _aux: MappingProxyType

    def __init__(
        self,
        *,
        as_of: date,
        prices: MappingProxyType,  # Mapping[str, pl.DataFrame]
        fundamentals: MappingProxyType,  # Mapping[str, tuple]
        aux: MappingProxyType,
    ) -> None:
        object.__setattr__(self, "_as_of", as_of)
        object.__setattr__(self, "_prices", prices)
        object.__setattr__(self, "_fundamentals", fundamentals)
        object.__setattr__(self, "_aux", aux)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ModelInputs is read-only")

    @property
    def as_of(self) -> date:
        """All data in this bundle is dated on or before this date."""
        return self._as_of

    @property
    def prices(self) -> MappingProxyType:
        """Mapping symbol -> raw price frame (SHALLOW read-only)."""
        return self._prices

    @property
    def fundamentals(self) -> MappingProxyType:
        """Mapping symbol -> tuple of fundamental records (SHALLOW read-only)."""
        return self._fundamentals

    @property
    def aux(self) -> MappingProxyType:
        """Optional auxiliary data (e.g. benchmark frames) (SHALLOW read-only)."""
        return self._aux

    def prices_for(self, symbol: str) -> pl.DataFrame:
        """Price frame for one symbol; KeyError if absent."""
        frame: pl.DataFrame = self._prices[symbol]
        return frame
