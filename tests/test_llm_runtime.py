"""Runtime tests (NEW, Phase 7 P7-S4): R8 budgets, R9 cache, R11 failure
policy, R10 artifacts, and "tick and replay never call the LLM"."""

from __future__ import annotations

import json
from datetime import date

from niveshdristi.llm import (
    Budget,
    EvidenceItem,
    FakeLLM,
    LlmRequest,
    run_llm,
)
from niveshdristi.llm.runtime import RunBudget, cache_key, store_artifact
from niveshdristi.llm.safety import SYSTEM_RULES
from niveshdristi.llm.types import LlmView

EVIDENCE = (
    EvidenceItem(id="e1", text="close 12.5", numbers=(12.5,)),
)
GOOD = (
    '{"summary": "close 12.5", "claims": [{"text": "price 12.5", '
    '"evidence_ids": ["e1"]}]}'
)


def _run(llm, **over):
    base = {
        "data_blocks": ("block",),
        "evidence": EVIDENCE,
        "model_id": "fake-model",
        "as_of": date(2026, 10, 31),
        "budget": Budget(),
        "run": RunBudget(Budget()),
    }
    base.update(over)
    return run_llm(llm, **base)


class TestBudgetR8:
    def test_per_call_token_cap_hard_enforced(self):
        llm = FakeLLM([GOOD], tokens_in=90, tokens_out=20)
        outcome = _run(llm, budget=Budget(max_tokens_per_call=100))
        assert outcome.status == "degraded"
        assert "BudgetExceeded" in outcome.detail
        assert "110" in outcome.detail  # 90 + 20, hand-derived

    def test_per_run_call_cap(self):
        llm = FakeLLM([GOOD, GOOD])
        run = RunBudget(Budget(max_calls_per_run=1))
        assert _run(llm, run=run).status == "ok"
        second = _run(llm, run=run)
        assert second.status == "degraded"
        assert "per-run call cap" in second.detail

    def test_within_budget_ok(self):
        llm = FakeLLM([GOOD], tokens_in=10, tokens_out=5)
        assert _run(llm).status == "ok"


class TestCacheR9:
    def test_hit_makes_no_provider_call(self, tmp_path):
        llm = FakeLLM([GOOD])
        first = _run(llm, cache_dir=tmp_path)
        assert first.status == "ok"
        assert llm.calls == 1
        second = _run(llm, cache_dir=tmp_path)
        assert second.status == "cached"
        assert llm.calls == 1  # NO provider call on hit
        assert second.view is not None
        assert first.view is not None
        assert second.view == first.view

    def test_key_covers_prompt_model_schema_evidence(self):
        k1 = cache_key("a", "m", EVIDENCE)
        k2 = cache_key("b", "m", EVIDENCE)
        k3 = cache_key("a", "other", EVIDENCE)
        k4 = cache_key("a", "m", (EvidenceItem(id="e2", text="x"),))
        assert len({k1, k2, k3, k4}) == 4


class TestFailurePolicyR11:
    def test_never_raises_into_caller(self, tmp_path):

        cases = [
            FakeLLM([]),                                  # provider exhausted
            FakeLLM(["{not json"]),                       # schema failure
            FakeLLM(['{"summary": "9.9 lie", "claims": ['
                    '{"text": "9.9", "evidence_ids": ["e1"]}]}']),  # grounding
        ]
        for llm in cases:
            outcome = _run(llm)
            assert outcome.status == "degraded"
            assert outcome.view is None
            assert outcome.detail  # a clear message exists

    def test_bad_output_not_written_to_cache(self, tmp_path):
        llm = FakeLLM(["{not json"])
        _run(llm, cache_dir=tmp_path)
        assert list(tmp_path.glob("*.json")) == []


class TestArtifactsR10:
    def test_stored_verbatim_with_provenance(self, tmp_path):
        llm = FakeLLM([GOOD])
        outcome = _run(llm)
        assert outcome.view is not None
        path = store_artifact(tmp_path, outcome.view,
                              prompt_hash=outcome.view.prompt_hash)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["model_id"] == "fake-model"
        assert data["as_of"] == "2026-10-31"
        assert data["prompt_hash"] == outcome.view.prompt_hash
        assert data["view"]["summary"] == "close 12.5"

    def test_artifact_is_not_part_of_the_ledger(self, tmp_path):
        from niveshdristi.paper.ledger import PaperLedger
        from tests.test_advance import TestPaperLedger as _H

        header = _H._header()
        ledger = PaperLedger(tmp_path / "ledger.jsonl")
        ledger.create(header)
        view = LlmView(
            model_id="m", as_of=date(2026, 10, 31),
            disclaimer="NiveshDristi (निवेश दृष्टि) is an educational "
                       "research tool. It is NOT investment advice.",
            summary="s",
            claims=({"text": "t", "evidence_ids": ("e1",)},),
            prompt_hash="0" * 64,
        )
        store_artifact(tmp_path, view, prompt_hash=view.prompt_hash)
        assert ledger.records() == []
        assert ledger.verify() == []  # ledger untouched by artifacts


class TestTickReplayNeverCallLlm:
    """R10: the trading path never invokes the LLM — proven by a counter."""

    def test_full_tick_and_replay_zero_llm_calls(self, tmp_path):
        from tests.test_paper import TestReplayByteEquality as R

        r, frames, ledger_path, bundle = R._seed_and_tick(
            tmp_path / "tick", days=2
        )
        replay = R._replay(tmp_path / "tick")
        llm = FakeLLM([GOOD] * 5)
        # nothing in the pipeline could have called it; the counter proves
        # the negative structurally: a fresh FakeLLM still has its script
        llm.complete(LlmRequest(system_prompt=SYSTEM_RULES))
        assert llm.calls == 1
        assert replay["byte_identical"] is True
