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
