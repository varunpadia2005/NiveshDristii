"""Signal vocabulary (NEW, P8-S4, BINDING).

Icon + word, never colour alone. Thresholds are named UNVALIDATED DEFAULT
constants. The words buy, sell, hold, swap, recommend and advice NEVER
appear in any label output (tested by grep)."""

from __future__ import annotations

from typing import Any

# UNVALIDATED DEFAULTS: lean thresholds, not tuned values.
LEAN_POSITIVE = 0.2
LEAN_NEGATIVE = -0.2

ICON_UP = "\u25b2"      # ▲ up
ICON_DOWN = "\u25bc"    # ▼ down
ICON_NEUTRAL = "\u2014"  # — dash

CONVICTION_CAPTION = "Conviction (uncalibrated, -1 to +1)"


def lean_label(conviction: float | None) -> str:
    """Conviction -> vocabulary label (icon + word). Hand-derived:
    +0.5 -> '▲ Positive lean'; -0.5 -> '▼ Negative lean'; 0.0 -> '— Neutral';
    None -> 'No opinion'."""
    if conviction is None:
        return "No opinion"
    if conviction >= LEAN_POSITIVE:
        return f"{ICON_UP} Positive lean"
    if conviction <= LEAN_NEGATIVE:
        return f"{ICON_DOWN} Negative lean"
    return f"{ICON_NEUTRAL} Neutral"


def negative_qualifier(*, long_only: bool, held: bool) -> str:
    """Qualifier appended to a negative lean when the position cannot be
    held: 'not held under long-only'."""
    if long_only and not held:
        return "not held under long-only"
    return ""


def model_status_label(model: Any) -> str:
    """Registry status -> label. data_status 'stub' -> 'Stub: not computed';
    evidence-only models -> 'Evidence only'; live models produce lean
    labels via lean_label()."""
    status = getattr(model, "data_status", None) or (
        model.registry_entry().data_status
        if hasattr(model, "registry_entry") else None
    )
    if status == "stub":
        return "Stub: not computed"
    if status == "evidence_only":
        return "Evidence only"
    return ""  # live: use lean_label on the produced conviction
