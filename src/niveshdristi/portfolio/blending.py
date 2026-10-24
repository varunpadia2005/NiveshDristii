"""Strategy blending policy (NEW, Phase 4) — pure function.

Takes a parsed strategy mapping (from the EXISTING config_loader strategy
YAML loading — no config_loader edits) and Signals, and produces blended
convictions as FIXED LINEAR WEIGHTS over model ids.

PLAIN STATEMENT: linear weights over UNCALIBRATED, UNVALIDATED signals.
These are NOT probabilities, and blended values must not be interpreted as
probabilities; calibration belongs to the Phase 5 validation gate.

Validation: weights non-negative; every model id must exist in the
registry's known ids (passed in — no registry import here); unknown ids
raise; ids missing from the signals are handled explicitly (their weight is
redistributed proportionally); weights are normalised to sum to 1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULT (only used for equal_weight policy semantics)
_EPS = 1e-12


def blend_convictions(
    models: Sequence[Mapping[str, object]],
    signals: Sequence[Signal],
    *,
    known_model_ids: set[str],
) -> dict[str, float]:
    """Blend per-symbol convictions with fixed linear weights.

    Args:
        models: parsed strategy models list: each {model_id, weight, ...}.
        signals: the signals to blend (grouped internally by symbol).
        known_model_ids: registry ids the strategy may reference.

    Returns:
        symbol -> blended conviction in [-1, 1].
    """
    ids: list[str] = []
    weights: list[float] = []
    for entry in models:
        model_id = str(entry.get("model_id", ""))
        raw_weight = entry.get("weight", 0.0)
        weight = float(raw_weight) if isinstance(raw_weight, (int, float)) else 0.0
        if model_id not in known_model_ids:
            raise ConfigurationError(
                f"strategy references unknown model_id {model_id!r}"
            )
        if weight < 0:
            raise ConfigurationError(f"negative weight for {model_id!r}")
        ids.append(model_id)
        weights.append(weight)
    if not ids:
        raise ConfigurationError("strategy has no models")
    total = sum(weights)
    if total <= 0:
        raise ConfigurationError("strategy weights must sum to a positive value")
    weight_by_id = {mid: w / total for mid, w in zip(ids, weights, strict=True)}

    # Group signals per symbol; a model may be absent for a symbol (missing
    # ids handled explicitly: weight redistributed among present models).
    per_symbol: dict[str, list[Signal]] = {}
    for s in signals:
        per_symbol.setdefault(s.instrument.symbol, []).append(s)

    blended: dict[str, float] = {}
    for symbol, sigs in per_symbol.items():
        used_weight = 0.0
        acc = 0.0
        for s in sigs:
            w = weight_by_id.get(s.model_id)
            if w is None:
                continue
            acc += w * s.conviction
            used_weight += w
        if used_weight <= 0:
            continue  # no known model signalled this symbol
        blended[symbol] = acc / used_weight  # redistribute missing weight
    return blended
