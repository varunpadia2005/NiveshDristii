"""Scriptable FakeLLM (NEW, Phase 7).

Deterministic test double: returns scripted outputs in order, reports fixed
token counts (R8 determinism), records every request so tests can prove
who called the LLM and how often (cache-hit counter test, tick/replay
never-call test).
"""

from __future__ import annotations

from niveshdristi.llm.errors import LlmProviderError
from niveshdristi.llm.types import LlmRequest, LlmResponse


class FakeLLM:
    """Scripted provider. outputs are returned one per call; token counts
    are constant so budget math is hand-checkable."""

    def __init__(
        self,
        outputs: list[str] | None = None,
        *,
        tokens_in: int = 10,
        tokens_out: int = 5,
        model_id: str = "fake-model",
    ) -> None:
        # no script -> a single empty-JSON placeholder so a factory-built
        # FakeLLM still completes once (tests script their own outputs)
        self._outputs = list(outputs) if outputs is not None else ["{}"]
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self.model_id = model_id
        self.calls = 0
        self.requests: list[LlmRequest] = []

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.calls += 1
        self.requests.append(request)
        if not self._outputs:
            raise LlmProviderError("FakeLLM script exhausted")
        return LlmResponse(
            text=self._outputs.pop(0),
            model_id=self.model_id,
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
        )
