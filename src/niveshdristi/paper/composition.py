"""Fund composition recording and replay (NEW, FX-A).

A fund's model/limits/rebalance composition is RECORDED at creation in the
ledger header (line 1, OUTSIDE the hash chain — verify() skips it and
record hashes never cover it). Tick and replay use the recorded
composition from then on; they never silently substitute.

If a recorded model id is missing from the known classes, or its
parameter digest differs from the current code, `compose_from_recorded`
raises CompositionError naming the model and the difference — it never
substitutes silently.

Funds created before this change have no composition field: replay still
runs with the CURRENT composition, but callers must surface
composition_recorded: false (the caller decides whether to warn).
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

from niveshdristi.core.errors import LedgerError


class CompositionError(LedgerError):
    """A recorded composition cannot be honoured: a model id is missing
    from the known classes, or its parameter digest differs from the
    current code."""


def model_param_digest(model: Any) -> str:
    """sha256 over the model's registry entry and its module-level
    UPPERCASE parameter constants. Deterministic for a given code state;
    flips when any constant or registry field changes."""
    entry = model.registry_entry().model_dump(mode="json")
    module = sys.modules[type(model).__module__]
    consts: dict[str, str] = {}
    for name, value in sorted(vars(module).items()):
        if name.isupper() and isinstance(
            value, (int, float, str, bool, tuple, frozenset)
        ):
            consts[name] = repr(value)
    payload = json.dumps(
        {"entry": entry, "consts": consts}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _limits_digest(limits: Any) -> str:
    return hashlib.sha256(
        json.dumps(limits.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


def _rebalance_digest(rebalance: Any) -> str:
    return hashlib.sha256(
        repr(
            (
                rebalance.every_n_sessions,
                rebalance.first_session_on,
            )
        ).encode()
    ).hexdigest()


def record_composition(
    models: Any, limits: Any, rebalance: Any
) -> dict[str, Any]:
    """Build the composition header field from the live bundle + limits +
    rebalance. models is a ModelBundle (iterable of model objects)."""
    entries = []
    for model in models.models:
        entries.append({
            "model_id": model.model_id,
            "param_digest": model_param_digest(model),
        })
    return {
        "models": entries,
        "limits_digest": _limits_digest(limits),
        "rebalance_digest": _rebalance_digest(rebalance),
        "price_basis": "adjusted",
    }


def _known_model_classes() -> dict[str, type]:
    """model_id -> class for every REGISTERED live model. New models
    registered later are picked up here but are IGNORED for funds whose
    recorded composition predates them."""
    classes: dict[str, type] = {}
    from niveshdristi.alpha.quant.earnings_drift import EarningsDrift
    from niveshdristi.alpha.quant.fundamental_guardrails import FundamentalGuardrails
    from niveshdristi.alpha.quant.low_volatility import LowVolatility
    from niveshdristi.alpha.quant.mean_reversion import MeanReversion
    from niveshdristi.alpha.quant.momentum import (
        CrossSectionalMomentum,
        TimeSeriesMomentum,
    )
    from niveshdristi.alpha.quant.price_range import PriceRangeModel
    from niveshdristi.alpha.quant.quality_value import QualityValue
    from niveshdristi.alpha.quant.regime import RegimeModel
    from niveshdristi.alpha.quant.sector_rotation import SectorRotation
    from niveshdristi.alpha.quant.ta_ensemble import TaEnsemble

    for cls in (TimeSeriesMomentum, CrossSectionalMomentum, MeanReversion,
                LowVolatility, PriceRangeModel, RegimeModel, TaEnsemble,
                EarningsDrift, FundamentalGuardrails, QualityValue,
                SectorRotation):
        classes[cls().model_id] = cls
    return classes


def compose_from_recorded(
    composition: dict[str, Any],
    *,
    _ignore_recorded: bool = False,
) -> tuple[Any, Any, Any]:
    """Rebuild (ModelBundle, GateLimits, RebalanceSchedule) from a recorded
    composition. REFUSES with CompositionError if a model id is missing
    from the known classes or its param digest differs from the current
    code — never substitutes silently."""
    from niveshdristi.engine.advance import ModelBundle
    from niveshdristi.portfolio.risk_gates import GateLimits

    known = _known_model_classes()
    if _ignore_recorded:
        models = [cls() for cls in known.values()]
        from niveshdristi.portfolio.risk_gates import GateLimits
        from niveshdristi.engine.advance import RebalanceSchedule
        return ModelBundle(models), GateLimits(), RebalanceSchedule()
    models = []
    for entry in composition.get("models", []):
        mid = entry["model_id"]
        digest = entry["param_digest"]
        if mid not in known:
            raise CompositionError(
                f"recorded model {mid!r} is not in the known model classes; "
                f"cannot compose (available: {sorted(known)})"
            )
        instance = known[mid]()
        current = model_param_digest(instance)
        if current != digest:
            raise CompositionError(
                f"recorded model {mid!r} param digest {digest[:16]} differs "
                f"from current code digest {current[:16]}; the model's "
                f"constants or registry entry changed since the fund was "
                f"created"
            )
        models.append(instance)

    limits = GateLimits()
    if _limits_digest(limits) != composition.get("limits_digest"):
        raise CompositionError(
            "GateLimits digest differs from the recorded composition; "
            "the default limits changed since the fund was created"
        )
    from niveshdristi.engine.advance import RebalanceSchedule

    rebalance = RebalanceSchedule()
    if _rebalance_digest(rebalance) != composition.get("rebalance_digest"):
        raise CompositionError(
            "RebalanceSchedule digest differs from the recorded composition"
        )
    return ModelBundle(models), limits, rebalance
