"""Signal — alpha model output with conviction, thesis, and evidence."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from niveshdristi.core.instrument import Instrument


@dataclass(frozen=True, slots=True)
class Signal:
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

    instrument: Instrument
    as_of: datetime
    conviction: float
    horizon_days: int
    thesis: str
    evidence: dict[str, float | int | str] = field(default_factory=dict)
    model_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not -1.0 <= self.conviction <= 1.0:
            raise ValueError(f"conviction must be in [-1, +1], got {self.conviction}")
        if self.horizon_days < 1:
            raise ValueError(f"horizon_days must be >= 1, got {self.horizon_days}")
        if not self.thesis or not self.thesis.strip():
            raise ValueError("thesis cannot be empty")
        if not self.model_id:
            raise ValueError("model_id cannot be empty")

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
        direction = "LONG" if self.conviction > 0 else "SHORT" if self.conviction < 0 else "NEUTRAL"
        return f"Signal({self.instrument.symbol}, {direction}, conviction={self.conviction:.2f}, horizon={self.horizon_days}d)"