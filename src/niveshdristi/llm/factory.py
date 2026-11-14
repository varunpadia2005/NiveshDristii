"""make_llm factory (NEW, Phase 7).

R14: no provider names or model ids hard-coded outside this small registry
table. VERIFY NOTE: provider model ids change frequently and are NOT
asserted to exist anywhere; live providers are unverified (see
docs/VERIFY.md) and real HTTP lives only in tools/probe_llm.py (R13).
"""

from __future__ import annotations

from niveshdristi.llm.errors import LlmConfigError
from niveshdristi.llm.fake import FakeLLM
from niveshdristi.llm.types import LLM

# VERIFY (R14): the only REGISTERED provider is the test double. Real
# providers (anthropic / openai / google / ollama per docs) are NOT
# registered in Phase 7: their model ids, terms and endpoints are
# unverified, and R13 keeps real HTTP out of the package. Requesting one
# raises LlmConfigError rather than silently faking it.
PROVIDER_REGISTRY: dict[str, type] = {
    "fake": FakeLLM,
}


def make_llm(provider: str, model: str) -> LLM:
    """Return an LLM for a REGISTERED provider; unknown -> LlmConfigError."""
    if provider not in PROVIDER_REGISTRY:
        raise LlmConfigError(
            f"unknown LLM provider: {provider!r} "
            f"(registered: {sorted(PROVIDER_REGISTRY)})"
        )
    if not model:
        raise LlmConfigError("model id must be a non-empty string")
    cls: type = PROVIDER_REGISTRY[provider]
    instance: LLM = cls(model_id=model)  # type: ignore[no-any-return]
    return instance
