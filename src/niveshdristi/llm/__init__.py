"""LLM layer (NEW, Phase 7) — GenAI kept safely.

Structural separation (R1): this package imports only core/ + stdlib +
pydantic; portfolio/, execution/, engine/, paper/, marketdata/ and alpha/
must NEVER import it. LLM output exists as the frozen LlmView, which no
portfolio/execution/engine/paper function accepts (R1/R2); it enters only
as evidence text in reports/CLI explanations composed in cli/.
"""

from __future__ import annotations

from niveshdristi.llm.errors import (
    BudgetExceeded,
    LlmConfigError,
    LlmError,
    LlmGroundingError,
    LlmInjectionRejected,
    LlmProviderError,
    LlmSchemaError,
)
from niveshdristi.llm.factory import PROVIDER_REGISTRY, make_llm
from niveshdristi.llm.fake import FakeLLM
from niveshdristi.llm.types import (
    DISCLAIMER_TEXT,
    LLM,
    SCHEMA_VERSION,
    Budget,
    Claim,
    EvidenceItem,
    LlmRequest,
    LlmResponse,
    LlmView,
    data_block,
)

__all__ = [
    "BudgetExceeded",
    "Claim",
    "DISCLAIMER_TEXT",
    "EvidenceItem",
    "FakeLLM",
    "LLM",
    "LlmConfigError",
    "LlmError",
    "LlmGroundingError",
    "LlmInjectionRejected",
    "LlmProviderError",
    "LlmRequest",
    "LlmResponse",
    "LlmSchemaError",
    "LlmView",
    "PROVIDER_REGISTRY",
    "SCHEMA_VERSION",
    "Budget",
    "data_block",
    "make_llm",
]
