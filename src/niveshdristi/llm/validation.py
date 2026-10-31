"""Output validation (NEW, Phase 7 P7-S2).

R3: the LLM must return JSON; malformed output raises LlmSchemaError and is
NEVER repaired. R4: every claim must cite supplied evidence ids; unknown ids
raise LlmGroundingError; every numeric token in the output must be traceable
to a number of the CITED evidence items (a "lying LLM" that injects a fake
number is rejected). R12: the returned LlmView always carries the official
DISCLAIMER_TEXT and the caller-supplied as_of date (never a clock read).
"""

from __future__ import annotations

import json
import re
from datetime import date

from niveshdristi.llm.errors import LlmGroundingError, LlmSchemaError
from niveshdristi.llm.types import (
    DISCLAIMER_TEXT,
    SCHEMA_VERSION,
    Claim,
    EvidenceItem,
    LlmView,
)

# Numeric tokens NOT embedded in identifiers ("e2" is an id, not the number
# 2): digit runs must not be preceded/followed by word characters or dots
# that belong to a longer token.
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

EXPECTED_OUTPUT_SHAPE = {
    "summary": "string",
    "claims": [{"text": "string", "evidence_ids": ["string", ...]}],
}


def _numeric_tokens(text: str) -> list[float]:
    return [float(m) for m in _NUM.findall(text)]


def validate_output(
    raw: str,
    evidence: tuple[EvidenceItem, ...],
    *,
    model_id: str,
    as_of: date,
    prompt_hash: str,
) -> LlmView:
    """Strict pipeline: JSON -> schema -> grounding -> LlmView.

    Raises LlmSchemaError (malformed JSON / wrong shape) or
    LlmGroundingError (unknown evidence id, uncited claim, or a numeric
    token not present in the CITED evidence). Never repairs silently.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LlmSchemaError(f"output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmSchemaError("output must be a JSON object")
    unknown_keys = set(data) - {"summary", "claims"}
    if unknown_keys:
        raise LlmSchemaError(f"unexpected output keys: {sorted(unknown_keys)}")
    if not isinstance(data.get("summary"), str) or not data["summary"].strip():
        raise LlmSchemaError("summary must be a non-empty string")
    claims_raw = data.get("claims")
    if not isinstance(claims_raw, list) or not claims_raw:
        raise LlmSchemaError("claims must be a non-empty list")

    by_id = {e.id: e for e in evidence}
    claims: list[Claim] = []
    for i, c in enumerate(claims_raw):
        if not isinstance(c, dict) or set(c) != {"text", "evidence_ids"}:
            raise LlmSchemaError(f"claim {i} must have exactly text + evidence_ids")
        text, ids = c["text"], c["evidence_ids"]
        if not isinstance(text, str) or not text.strip():
            raise LlmSchemaError(f"claim {i} text must be a non-empty string")
        if not isinstance(ids, list) or not ids:
            raise LlmSchemaError(f"claim {i} must cite at least one evidence id")
        cited_numbers: set[float] = set()
        for eid in ids:
            if eid not in by_id:
                raise LlmGroundingError(
                    f"claim {i} cites unknown evidence id {eid!r}"
                )
            cited_numbers.update(by_id[eid].numbers)
        for num in _numeric_tokens(text):
            if num not in cited_numbers:
                raise LlmGroundingError(
                    f"claim {i} uses number {num} not present in its cited "
                    f"evidence {sorted(ids)}"
                )
        claims.append(Claim(text=text, evidence_ids=tuple(ids)))

    # The summary is part of the view but numbers there are NOT exempt (R4):
    # they must be traceable to ANY supplied evidence (it is not claim-scoped).
    all_numbers = {n for e in evidence for n in e.numbers}
    for num in _numeric_tokens(data["summary"]):
        if num not in all_numbers:
            raise LlmGroundingError(
                f"summary uses number {num} not present in any supplied evidence"
            )

    return LlmView(
        model_id=model_id,
        as_of=as_of,
        disclaimer=DISCLAIMER_TEXT,
        summary=data["summary"],
        claims=tuple(claims),
        prompt_hash=prompt_hash,
        schema_version=SCHEMA_VERSION,
    )
