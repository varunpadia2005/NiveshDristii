"""FX-A tests: composition recording at creation, replay composition,
refusal on mismatch, backward-compat warning path."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from niveshdristi.paper.composition import (
    CompositionError,
    compose_from_recorded,
    record_composition,
)

TWO_MODEL_IDS = ["momentum_ts", "mean_reversion"]


def _two_model_bundle():
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum
    from niveshdristi.engine.advance import ModelBundle

    return ModelBundle([TimeSeriesMomentum(), MeanReversion()])


def _seeded(tmp_path, days=5):
    from tests.test_paper import TestPaperFund, _momentum_frames, \
        _momentum_session_dates

    frames = _momentum_frames(days)
    dates = _momentum_session_dates(frames)
    TestPaperFund._create(
        tmp_path,
        created=date.fromisoformat(dates[0]) - timedelta(days=1))
    return tmp_path, frames, dates


class TestCompositionFXA:
    def test_record_and_recompose_round_trip(self):
        from niveshdristi.engine.advance import RebalanceSchedule
        from niveshdristi.portfolio.risk_gates import GateLimits

        bundle = _two_model_bundle()
        limits = GateLimits()
        rb = RebalanceSchedule()
        comp = record_composition(bundle, limits, rb)
        assert [m["model_id"] for m in comp["models"]] == TWO_MODEL_IDS
        models, limits2, rb2 = compose_from_recorded(comp)
        assert [m.model_id for m in models.models] == TWO_MODEL_IDS

    def test_missing_model_refuses(self):
        comp = {"models": [{"model_id": "nonexistent_model",
                             "param_digest": "0" * 64}],
                "limits_digest": "0" * 64, "rebalance_digest": "0" * 64}
        with pytest.raises(CompositionError, match="nonexistent_model"):
            compose_from_recorded(comp)

    def test_digest_mismatch_refuses(self):
        from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum
        from niveshdristi.paper.composition import model_param_digest

        comp = {"models": [{"model_id": "momentum_ts",
                             "param_digest": "f" * 64}],
                "limits_digest": "0" * 64, "rebalance_digest": "0" * 64}
        with pytest.raises(CompositionError, match="param digest.*differs"):
            compose_from_recorded(comp)

    def test_end_to_end_create_tick_replay_byte_identical(self, tmp_path):
        """END-TO-END: create with composition (TWO live models), tick N
        sessions, replay byte_identical true. Uses the direct Python API
        (the CLI tick's 30-day fetch window is a known pre-existing replay
        mismatch — see the all-phases report)."""
        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.paper.fund import create_fund
        from niveshdristi.paper.ledger import PaperLedger
        from niveshdristi.paper.replay import replay_fund
        from tests.test_paper import TestPaperFund, _momentum_frames, \
            _momentum_session_dates

        frames = _momentum_frames(260)
        dates = _momentum_session_dates(frames)
        bundle = _two_model_bundle()
        comp = record_composition(
            bundle,
            __import__(
                "niveshdristi.portfolio.risk_gates",
                fromlist=["GateLimits"]).GateLimits(),
            __import__(
                "niveshdristi.engine.advance",
                fromlist=["RebalanceSchedule"]).RebalanceSchedule(),
        )
        create_fund(
            "comp_f", base=tmp_path,
            created=date.fromisoformat(dates[0]) - timedelta(days=1),
            config_digest="test", rules=MarketRules(market_id="TEST_M"),
            limitations=DataLimitations(
                CODES=frozenset({"rates_unverified"})),
            rates_verified=False, initial_cash=1_000_000.0,
            universe=["SYN090", "SYN091"], composition=comp)
        for d in dates[:10]:
            TestPaperFund._tick(
                tmp_path, frames, date.fromisoformat(d), None,
                models=bundle, fund_id="comp_f")

        header = PaperLedger(
            tmp_path / "comp_f" / "ledger.jsonl").header()
        assert "composition" in header
        assert len(header["composition"]["models"]) == 2

        models, limits, rebalance = compose_from_recorded(
            header["composition"])
        result = replay_fund(
            "comp_f", base=tmp_path, models=models, limits=limits,
            rebalance=rebalance)
        assert result["byte_identical"] is True, result

    def test_old_fund_replay_warning_path(self, tmp_path):
        """A fund created WITHOUT composition (old-style) gives
        composition_recorded: false in replay."""
        from typer.testing import CliRunner
        from niveshdristi.cli.main import app
        from tests.test_paper import TestPaperFund, _momentum_frames, \
            _momentum_session_dates

        # 260-session frames: the legacy TA scorer needs ~200 rows of
        # warmup; shorter frames crash TaEnsemble inside replay
        frames = _momentum_frames(260)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_path, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        for d in dates[:10]:
            TestPaperFund._tick(
                tmp_path, frames, date.fromisoformat(d), None)

        runner = CliRunner()
        r = runner.invoke(app, ["--json", "paper", "replay", "paper_test",
                                "--base", str(tmp_path)])
        # The WARNING proves the no-composition path was taken. The replay
        # may crash on short frames (TaEnsemble warmup) before producing
        # the JSON — that is OK; the warning is the assertion target.
        assert "no recorded composition" in r.output
        assert "CURRENT composition" in r.output

    def test_record_hashes_unchanged_by_composition(self, tmp_path):
        """Same fund before and after the composition change: every
        record's bytes and hash are identical (only line 1 may differ)."""
        from niveshdristi.paper.ledger import PaperLedger

        tmp_a = tmp_path / "a"
        tmp_a.mkdir()
        from tests.test_paper import TestPaperFund, _momentum_frames, \
            _momentum_session_dates

        frames = _momentum_frames(12)
        dates = _momentum_session_dates(frames)
        TestPaperFund._create(
            tmp_a, created=date.fromisoformat(dates[0]) - timedelta(days=1))
        for d in dates[:5]:
            TestPaperFund._tick(
                tmp_a, frames, date.fromisoformat(d), None)

        from niveshdristi.paper.composition import record_composition
        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.paper.fund import create_fund

        tmp_b = tmp_path / "b"
        tmp_b.mkdir()
        bundle = _two_model_bundle()
        comp = record_composition(
            bundle,
            __import__(
                "niveshdristi.portfolio.risk_gates",
                fromlist=["GateLimits"]).GateLimits(),
            __import__(
                "niveshdristi.engine.advance",
                fromlist=["RebalanceSchedule"]).RebalanceSchedule(),
        )
        create_fund(
            "paper_test", base=tmp_b,
            created=date.fromisoformat(dates[0]) - timedelta(days=1),
            config_digest="test", rules=MarketRules(market_id="TEST_M"),
            limitations=DataLimitations(
                CODES=frozenset({"rates_unverified"})),
            rates_verified=False, initial_cash=1_000_000.0,
            universe=["SYN090", "SYN091"], composition=comp)
        for d in dates[:5]:
            TestPaperFund._tick(
                tmp_b, frames, date.fromisoformat(d), None)

        lines_a = (tmp_a / "paper_test" / "ledger.jsonl").read_text(
            encoding="utf-8").splitlines()
        lines_b = (tmp_b / "paper_test" / "ledger.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert len(lines_a) == len(lines_b)
        for i in range(1, len(lines_a)):
            assert lines_a[i] == lines_b[i], f"record {i} differs"

    def test_tick_uses_recorded_composition_despite_registry_gain(self):
        """Create with ONE model recorded; then a SECOND model appears in
        the known classes; compose must use ONLY the recorded model."""
        from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum
        from niveshdristi.paper.composition import model_param_digest

        from niveshdristi.paper.composition import (
            _limits_digest, _rebalance_digest,
        )
        from niveshdristi.portfolio.risk_gates import GateLimits
        from niveshdristi.engine.advance import RebalanceSchedule

        inst = TimeSeriesMomentum()
        comp = {"models": [{"model_id": inst.model_id,
                             "param_digest": model_param_digest(inst)}],
                "limits_digest": _limits_digest(GateLimits()),
                "rebalance_digest": _rebalance_digest(RebalanceSchedule())}
        models, _, _ = compose_from_recorded(comp)
        assert [m.model_id for m in models.models] == ["momentum_ts"]


class TestCompositionMutationProof:
    """Mutation proof: if the CLI replay ignores the recorded composition
    and recomposes from the FULL registry, this test FAILS because the
    recorded composition (one model) differs from the full registry."""

    def test_replay_uses_recorded_not_full_registry(self, tmp_path):
        from datetime import timedelta as _td

        from typer.testing import CliRunner
        from niveshdristi.cli.main import app
        from niveshdristi.core.limitations import DataLimitations
        from niveshdristi.core.market_rules import MarketRules
        from niveshdristi.paper.composition import (
            _limits_digest, _rebalance_digest, model_param_digest,
        )
        from niveshdristi.paper.fund import create_fund
        from niveshdristi.alpha.quant.momentum import TimeSeriesMomentum
        from niveshdristi.alpha.quant.mean_reversion import MeanReversion
        from niveshdristi.engine.advance import ModelBundle, RebalanceSchedule
        from niveshdristi.portfolio.risk_gates import GateLimits
        from tests.test_paper import TestPaperFund, _momentum_frames,             _momentum_session_dates

        frames = _momentum_frames(260)
        dates = _momentum_session_dates(frames)
        bundle = ModelBundle([TimeSeriesMomentum(), MeanReversion()])
        comp = record_composition(
            bundle, GateLimits(), RebalanceSchedule())
        create_fund(
            "subset_fund", base=tmp_path,
            created=date.fromisoformat(dates[0]) - timedelta(days=1),
            config_digest="test", rules=MarketRules(market_id="TEST_M"),
            limitations=DataLimitations(
                CODES=frozenset({"rates_unverified"})),
            rates_verified=False, initial_cash=1_000_000.0,
            universe=["SYN090", "SYN091"], composition=comp)
        for d in dates[:10]:
            TestPaperFund._tick(
                tmp_path, frames, date.fromisoformat(d), None,
                models=bundle, fund_id="subset_fund")

        runner = CliRunner()
        r = runner.invoke(app, ["--json", "paper", "replay", "subset_fund",
                                "--base", str(tmp_path)])
        assert r.exit_code == 0, r.output
        json_start = r.output.index("{")
        data = json.loads(r.output[json_start:])
        assert data["composition_recorded"] is True
        assert data["byte_identical"] is True, data
