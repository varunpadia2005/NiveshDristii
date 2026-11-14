"""Typed LLM errors (NEW, Phase 7).

Every failure mode named by the binding design rules has its own type; the
failure policy (R11) degrades to a logged no-op and never lets these escape
into a tick, a backtest or a report build.
"""

from __future__ import annotations


class LlmError(Exception):
    """Base type for every LLM-layer failure."""


class LlmConfigError(LlmError):
    """Unknown provider, bad factory arguments, non-callable sink."""


class LlmProviderError(LlmError):
    """Provider down, transport failure, or scripted provider exhausted."""


class LlmSchemaError(LlmError):
    """Output did not validate against the pydantic schema (R3).

    Malformed output is REJECTED, never repaired silently.
    """


class LlmGroundingError(LlmError):
    """Output cites unknown evidence ids, uncited claims, or numbers not
    traceable to the cited evidence (R4)."""


class BudgetExceeded(LlmError):
    """Token or call cap enforced hard (R8); named by the binding rules."""


class LlmInjectionRejected(LlmError):
    """Output that could only have come from treating a DATA block as
    instructions (R5); rejected by the validators, never executed."""
