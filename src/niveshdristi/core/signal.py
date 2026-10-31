"""Signal — alpha model output with conviction, thesis, and evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict

from niveshdristi.core.instrument import Instrument


class Signal(BaseModel):
    """
    Immutable signal from an AlphaModel.

    Attributes:
        instrument: The instrument this signal applies to
        as_of: Point-in-time timestamp — only data available at this time may be used
        conviction: Conviction strength in [-1, +1]
            - Negative = bearish (clamped to 0 for long-only markets at portfolio construction)
            - 0 = neutral
            - Positive = bullish
        horizon_days: Expected holding period / signal validity window
        thesis: Plain-English explanation of the signal rationale
        evidence: Key-value pairs of the numeric/factual evidence supporting the thesis
            All numbers cited in thesis MUST appear here (enforced by GroundingValidator)
        model_id: Unique identifier of the AlphaModel that produced this signal
        metadata: Additional model-specific data (not validated for grounding)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    as_of: datetime
    conviction: float = Field(..., ge=-1.0, le=1.0)
    horizon_days: int = Field(..., ge=1)
    thesis: str = Field(..., min_length=1)
    evidence: dict[str, float | int | str] = {}
    model_id: str = Field(..., min_length=1)
    metadata: dict[str, Any] = {}

    @field_validator("thesis", mode="before")
    @classmethod
    def _thesis_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("thesis cannot be empty")
        return v.strip()

    @field_validator("model_id", mode="before")
    @classmethod
    def _model_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model_id cannot be empty")
        return v.strip()

    def is_long(self, *, long_only: bool = True) -> bool:
        """Whether this signal represents a long position after market rules."""
        if long_only:
            return self.conviction > 0
        return self.conviction != 0

    def effective_conviction(self, *, long_only: bool = True) -> float:
        """Conviction after applying market rules (e.g., clamp negative to 0 for long-only)."""
        if long_only and self.conviction < 0:
            return 0.0
        return self.conviction

    def __str__(self) -> str:
        direction = (
            "LONG" if self.conviction > 0 else "SHORT" if self.conviction < 0 else "NEUTRAL"
        )
        return (
            f"Signal({self.instrument.symbol}, {direction}, "
            f"conviction={self.conviction:.2f}, horizon={self.horizon_days}d)"
        )
