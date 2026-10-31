"""LLM runtime: budgets, cache, failure policy, artifacts (NEW, P7-S4).

R8: hard token/call caps with the typed BudgetExceeded error; FakeLLM
reports token counts so the math is deterministic in tests.
R9: cache keyed by content hash (prompt + model id + schema version +
evidence hash) under a CALLER-SUPPLIED directory; a hit makes no provider
call.
R11: any provider/schema/grounding/budget failure degrades to a logged
no-op outcome — nothing raises into a tick, a backtest or a report build.
R10: LLM outputs are never part of hashed SessionRecords; an artifact is
stored verbatim (prompt hash, model id, as-of) under a caller-supplied
directory, separate from the ledger. Ticks and replay never call the LLM.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.config import ConfigDict

from niveshdristi.llm.errors import BudgetExceeded, LlmError
from niveshdristi.llm.safety import SYSTEM_RULES
from niveshdristi.llm.types import (
    LLM,
    SCHEMA_VERSION,
    Budget,
    EvidenceItem,
    LlmRequest,
    LlmView,
)
from niveshdristi.llm.validation import validate_output

ARTIFACT_FORMAT_VERSION = 1


class LlmOutcome(BaseModel):
    """Result of a guarded LLM run; `degraded` is the R11 no-op."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str  # "ok" | "cached" | "degraded"
    view: LlmView | None = None
    detail: str = ""


class RunBudget:
    """Per-run call counter enforcing Budget.max_calls_per_run (R8)."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.calls_made = 0


def _evidence_hash(evidence: tuple[EvidenceItem, ...]) -> str:
    payload = sorted(
        (e.id, e.text, sorted(e.numbers)) for e in evidence
    )
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def cache_key(
    prompt_text: str, model_id: str, evidence: tuple[EvidenceItem, ...]
) -> str:
    """R9 key: prompt + model id + schema version + evidence hash."""
    basis = json.dumps(
        [prompt_text, model_id, SCHEMA_VERSION, _evidence_hash(evidence)],
        sort_keys=True,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _load_cache(cache_dir: Path, key: str) -> LlmView | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return LlmView.model_validate(data["view"])


def _write_cache(cache_dir: Path, key: str, view: LlmView) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {"format_version": ARTIFACT_FORMAT_VERSION, "key": key,
             "view": json.loads(view.model_dump_json())},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def run_llm(
    llm: LLM,
    *,
    data_blocks: tuple[str, ...],
    evidence: tuple[EvidenceItem, ...],
    model_id: str,
    as_of: date,
    budget: Budget,
    run: RunBudget,
    cache_dir: str | Path | None = None,
    extra_system: str = "",
) -> LlmOutcome:
    """One guarded LLM call. NEVER raises (R11) — failures degrade."""
    prompt_text = json.dumps(
        [extra_system, list(data_blocks), sorted(e.id for e in evidence)],
        sort_keys=True,
    )
    key = cache_key(prompt_text, model_id, evidence)
    if cache_dir is not None:
        cached = _load_cache(Path(cache_dir), key)
        if cached is not None:
            return LlmOutcome(status="cached", view=cached,
                              detail=f"cache hit {key[:16]}")
    if run.calls_made >= run.budget.max_calls_per_run:
        return LlmOutcome(
            status="degraded", detail="BudgetExceeded: per-run call cap"
        )
    request = LlmRequest(
        system_prompt=(extra_system + "\n" + SYSTEM_RULES).strip(),
        data_blocks=data_blocks,
        schema_version=SCHEMA_VERSION,
        max_tokens=budget.max_tokens_per_call,
    )
    run.calls_made += 1
    try:
        response = llm.complete(request)
        tokens = response.tokens_in + response.tokens_out
        if tokens > budget.max_tokens_per_call:
            raise BudgetExceeded(
                f"call used {tokens} tokens > cap {budget.max_tokens_per_call}"
            )
        view = validate_output(
            response.text, evidence, model_id=response.model_id,
            as_of=as_of, prompt_hash=key,
        )
    except LlmError as exc:
        return LlmOutcome(status="degraded", detail=f"{type(exc).__name__}: {exc}")
    if cache_dir is not None:
        _write_cache(Path(cache_dir), key, view)
    return LlmOutcome(status="ok", view=view)


def store_artifact(
    directory: str | Path, view: LlmView, *, prompt_hash: str
) -> Path:
    """R10: verbatim recorded artifact, SEPARATE from the ledger."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"llm_artifact_{prompt_hash[:16]}.json"
    payload: dict[str, Any] = {
        "format_version": ARTIFACT_FORMAT_VERSION,
        "prompt_hash": prompt_hash,
        "model_id": view.model_id,
        "as_of": view.as_of.isoformat(),
        "view": json.loads(view.model_dump_json()),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path
