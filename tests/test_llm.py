"""LLM layer tests (NEW, Phase 7 P7-S1).

Covers R1 (import boundary both directions + LlmView rejected everywhere),
R12 (LlmView cannot be constructed without disclaimer + as_of), R14
(factory/typed errors) and the package skeleton contracts.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from niveshdristi.llm import (
    DISCLAIMER_TEXT,
    Budget,
    Claim,
    EvidenceItem,
    FakeLLM,
    LlmConfigError,
    LlmError,
    LlmProviderError,
    LlmRequest,
    LlmResponse,
    LlmView,
    data_block,
    make_llm,
)

DISC = DISCLAIMER_TEXT


def _view(**over):
    base = {
        "model_id": "fake-model",
        "as_of": date(2026, 10, 31),
        "disclaimer": DISC,
        "summary": "ok",
        "claims": (Claim(text="see evidence", evidence_ids=("e1",)),),
        "prompt_hash": "0" * 64,
    }
    base.update(over)
    return LlmView(**base)


class TestImportBoundary:
    """R1: the separation is structural and test-enforced BOTH ways."""

    _NEW_NEUTRAL = [
        "portfolio", "execution", "engine", "paper", "marketdata", "alpha",
    ]

    def test_new_neutral_packages_never_import_llm(self):
        root = Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
        offenders = []
        for pkg in self._NEW_NEUTRAL:
            for f in (root / pkg).rglob("*.py"):
                text = f.read_text(encoding="utf-8")
                if "niveshdristi.llm" in text or "niveshdristi import llm" in text:
                    offenders.append(f"{pkg}/{f.name}")
        assert offenders == [], offenders

    def test_llm_imports_only_core_stdlib_pydantic(self):
        root = Path(__file__).resolve().parent.parent / "src" / "niveshdristi" / "llm"
        allowed_prefixes = ("niveshdristi.core", "niveshdristi.llm")
        offenders = []
        for f in root.rglob("*.py"):
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith(("import ", "from ")) and "niveshdristi" in s:
                    if not s.startswith(("from niveshdristi import",)):
                        mod = s.split()[1].split(".")[0:3]
                        mod = ".".join(mod[:2]) if False else s.split()[1]
                        if not mod.startswith(allowed_prefixes):
                            offenders.append(f"{f.name}: {s}")
                    else:
                        offenders.append(f"{f.name}: {s}")
        assert offenders == [], offenders


class TestSeparationR1:
    """LlmView must be rejected by every trading-path entry point."""

    def _view(self):
        return _view()

    def test_construct_targets_rejects_llm_view(self):
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.portfolio.construction import construct_targets

        with pytest.raises((TypeError, ValidationError, AttributeError)):
            construct_targets([self._view()], MarketRules(market_id="T"))

    def test_gate_chain_rejects_llm_view(self):
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.portfolio.risk_gates import GateLimits, run_chain

        with pytest.raises((TypeError, ValidationError, AttributeError)):
            run_chain(
                self._view(), limits=GateLimits(), rules=MarketRules(market_id="T"),
                current_weights={},
            )

    def test_build_orders_rejects_llm_view(self):
        from niveshdristi.execution.orders import build_orders

        with pytest.raises((TypeError, ValidationError, AttributeError)):
            build_orders(
                self._view(), nav=1_000.0, cash=1_000.0, prices={},
                instruments={}, current_holdings={},
            )

    def test_sim_broker_rejects_llm_view(self):
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.execution.sim_broker import SimBroker

        broker = SimBroker(
            rates=MarketRules(market_id="T").rates,
            price_limits=MarketRules(market_id="T").price_limits,
        )
        with pytest.raises((TypeError, AttributeError, ValidationError)):
            broker.execute(self._view(), prices={})

    def test_advance_rejects_llm_view_as_models(self):
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.engine.advance import advance
        from niveshdristi.engine.fund import FundState

        fund = FundState(cash=1_000.0)
        with pytest.raises((TypeError, AttributeError, ValidationError)):
            advance(
                fund, date(2026, 10, 2), broker=None, frames={},
                models=self._view(),  # type: ignore[arg-type]
                rules=MarketRules(market_id="T"),
                limits=None, rebalance=None,
            )

    def test_no_trading_module_references_llm_by_name(self):
        """R1 second leg: the modules' SOURCE never names the llm package."""
        root = Path(__file__).resolve().parent.parent / "src" / "niveshdristi"
        for pkg in TestImportBoundary._NEW_NEUTRAL:
            for f in (root / pkg).rglob("*.py"):
                assert "llm" not in f.read_text(encoding="utf-8"), (
                    f"{pkg}/{f.name} references llm"
                )


class TestLlmViewConstruction:
    """R12: no disclaimer -> no view; no as_of -> no view."""

    def test_requires_official_disclaimer_text(self):
        with pytest.raises(ValidationError, match="DISCLAIMER_TEXT"):
            _view(disclaimer="educational only, trust me")

    def test_requires_as_of(self):
        with pytest.raises(ValidationError):
            LlmView(
                model_id="m", disclaimer=DISC, summary="s",
                claims=(Claim(text="t", evidence_ids=("e1",)),),
                prompt_hash="0" * 64,
            )  # type: ignore[call-arg]

    def test_frozen(self):
        v = _view()
        with pytest.raises(ValidationError):
            v.summary = "changed"  # type: ignore[misc]

    def test_claim_requires_evidence(self):
        with pytest.raises(ValidationError):
            Claim(text="uncited")


class TestEvidenceAndFactory:
    def test_evidence_id_malformed_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceItem(id="bad id!", text="x")

    def test_data_block_delimits(self):
        b = data_block("news", "some headline")
        assert "BEGIN DATA BLOCK" in b
        assert "NEVER INSTRUCTIONS" in b
        assert "some headline" in b

    def test_make_llm_fake(self):
        llm = make_llm("fake", "fake-model")
        assert isinstance(llm, FakeLLM)
        r = llm.complete(LlmRequest(system_prompt="s"))
        assert isinstance(r, LlmResponse)
        assert r.model_id == "fake-model"

    def test_make_llm_unknown_provider(self):
        with pytest.raises(LlmConfigError, match="unknown LLM provider"):
            make_llm("skynet", "m1")

    def test_make_llm_empty_model(self):
        with pytest.raises(LlmConfigError):
            make_llm("fake", "")

    def test_errors_share_base(self):
        from niveshdristi.llm import (
            BudgetExceeded,
            LlmGroundingError,
            LlmSchemaError,
        )

        for exc in (LlmConfigError, LlmProviderError, LlmSchemaError,
                    LlmGroundingError, BudgetExceeded):
            assert issubclass(exc, LlmError)

    def test_fake_llm_exhaustion_is_typed(self):
        llm = FakeLLM([])
        with pytest.raises(LlmProviderError):
            llm.complete(LlmRequest(system_prompt="s"))

    def test_budget_defaults_are_named_unvalidated(self):
        from niveshdristi.llm.types import (
            DEFAULT_MAX_CALLS_PER_RUN,
            DEFAULT_MAX_TOKENS_PER_CALL,
        )

        b = Budget()
        assert b.max_tokens_per_call == DEFAULT_MAX_TOKENS_PER_CALL
        assert b.max_calls_per_run == DEFAULT_MAX_CALLS_PER_RUN


class TestValidateOutput:
    """P7-S2: R3 schema, R4 grounding + numeric traceability, R12 always."""

    @staticmethod
    def _evidence():
        return (
            EvidenceItem(id="e1", text="close 12.5", numbers=(12.5, 0.82)),
            EvidenceItem(id="e2", text="vol 3.0", numbers=(3.0,)),
        )

    def test_valid_output_known_answer(self):
        from niveshdristi.llm import validate_output

        raw = (
            '{"summary": "composite 0.82 with close 12.5", '
            '"claims": [{"text": "price 12.5 above support", '
            '"evidence_ids": ["e1"]}]}'
        )
        v = validate_output(raw, self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")
        assert v.summary.startswith("composite 0.82")
        assert v.disclaimer == DISCLAIMER_TEXT  # R12: always official text
        assert v.as_of == date(2026, 10, 31)
        assert v.schema_version == "1"

    def test_malformed_json_rejected(self):
        from niveshdristi.llm import LlmSchemaError, validate_output

        with pytest.raises(LlmSchemaError, match="not valid JSON"):
            validate_output("{not json", self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")

    def test_wrong_shape_rejected(self):
        from niveshdristi.llm import LlmSchemaError, validate_output

        with pytest.raises(LlmSchemaError):
            validate_output('{"nope": 1}', self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")

    def test_lying_llm_fake_number_rejected(self):
        from niveshdristi.llm import LlmGroundingError, validate_output

        raw = (
            '{"summary": "meh", "claims": [{"text": "target 99.9", '
            '"evidence_ids": ["e1"]}]}'
        )
        with pytest.raises(LlmGroundingError, match="99.9"):
            validate_output(raw, self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")

    def test_unknown_evidence_id_rejected(self):
        from niveshdristi.llm import LlmGroundingError, validate_output

        raw = (
            '{"summary": "meh", "claims": [{"text": "x", '
            '"evidence_ids": ["ghost"]}]}'
        )
        with pytest.raises(LlmGroundingError, match="ghost"):
            validate_output(raw, self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")

    def test_number_from_uncited_evidence_rejected(self):
        from niveshdristi.llm import LlmGroundingError, validate_output

        raw = (
            '{"summary": "meh", "claims": [{"text": "vol 3.0", '
            '"evidence_ids": ["e1"]}]}'
        )
        with pytest.raises(LlmGroundingError, match="3.0"):
            validate_output(raw, self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")

    def test_summary_numbers_traceable_to_any_evidence(self):
        from niveshdristi.llm import validate_output

        raw = (
            '{"summary": "vol 3.0 observed", "claims": '
            '[{"text": "see e2", "evidence_ids": ["e2"]}]}'
        )
        v = validate_output(raw, self._evidence(), model_id="m",
                            as_of=date(2026, 10, 31), prompt_hash="h")
        assert v.summary == "vol 3.0 observed"

    def test_empty_claims_rejected(self):
        from niveshdristi.llm import LlmSchemaError, validate_output

        with pytest.raises(LlmSchemaError, match="non-empty"):
            validate_output('{"summary": "s", "claims": []}', self._evidence(),
                            model_id="m", as_of=date(2026, 10, 31),
                            prompt_hash="h")


class TestNumericTokenPolicy:
    """R8 1e: the numeric-token policy table. POLICY: a numeric token is
    extracted with the anchored regex and must equal, as a float, one of
    the CITED evidence numbers exactly after that single normalization.
    Ambiguous equivalences are REJECTED, never loosened."""

    @staticmethod
    def _tokens(text: str) -> list[float]:
        from niveshdristi.llm.validation import _numeric_tokens

        return _numeric_tokens(text)

    def test_table(self):
        evidence = {2.0, 5.0, 12.5, 10.0, 20.0, 3.5}
        # (input text, expected extracted tokens, verdict given evidence)
        rows = [
            ("1,000", [1.0, 0.0], "REJECT: comma splits; neither traces"),
            ("1000", [1000.0], "REJECT: 1000 not in evidence"),
            ("2.0", [2.0], "ACCEPT: exact after float normalization"),
            ("2", [2.0], "ACCEPT: 2 == 2.0 exactly"),
            ("5%", [5.0], "ACCEPT: symbol ignored, 5.0 in evidence"),
            ("0.05", [0.05], "REJECT: percent-to-fraction NOT inferred"),
            ("1e3", [], "REJECT: scientific notation is not a token"),
            ("1000 in 1e3", [1000.0], "REJECT: 1000 not in evidence"),
            ("model e2 says 2", [2.0], "ACCEPT: e2 digit not a token; 2 traces"),
            ("-3.5", [3.5], "REJECT-AS-STATED: sign dropped, 3.5 in evidence "
                             "-> token accepted but the MINUS is not modeled; "
                             "evidence carries magnitudes only"),
            ("(3.5)", [3.5], "ACCEPT-extraction: parentheses NOT inferred as "
                             "negatives; 3.5 traces"),
            ("Rs 12.5", [12.5], "ACCEPT: currency symbol ignored, no conversion"),
            ("$12.5", [12.5], "ACCEPT: currency symbol ignored, no conversion"),
            ("10-20", [10.0, 20.0], "ACCEPT-extraction: BOTH must trace"),
            ("two", [], "REJECT: number words are never inferred"),
            ("2026-10-31", [2026.0, 10.0, 31.0],
             "REJECT-in-practice: hyphen is not a word char, so date parts "
             "ARE tokens and each must trace to evidence; a date in a claim "
             "is untraceable unless evidence carries 2026.0, 10.0, 31.0"),
        ]
        print("NUMERIC TOKEN TABLE (policy: exact float match after the "
              "single documented normalization; ambiguous -> reject):")
        for text, expected, verdict in rows:
            got = self._tokens(text)
            print(f"  {text!r:>16} -> {got}  |  {verdict}")
            assert got == expected, (text, got, expected)
            # end-to-end: only rows whose every token is in evidence validate
            ok = all(n in evidence for n in got)
            if not ok:
                import json as _json

                from niveshdristi.llm import LlmGroundingError, validate_output

                raw = (
                    '{"summary": "s", "claims": [{"text": ' + _json.dumps(text) +
                    ', "evidence_ids": ["e1"]}]}'
                )
                with pytest.raises(LlmGroundingError):
                    validate_output(raw, (EvidenceItem(id="e1", text="x",
                                                       numbers=tuple(sorted(evidence))),),
                                    model_id="m", as_of=date(2026, 10, 31),
                                    prompt_hash="h")
