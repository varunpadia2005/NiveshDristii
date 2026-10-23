"""IN_NSE-specific alpha models (literal-free by design; symbols live in YAML).

Population mechanism (P3-S2): market packs expose register_all(registry),
called from a composition point OUTSIDE this package (CLI startup / engine
bootstrap / tests). The neutral alpha/registry never imports this package.
"""

from __future__ import annotations

from niveshdristi.alpha.registry import ModelRegistry
from niveshdristi.core.alpha import ModelRegistryEntry


def entries() -> list[ModelRegistryEntry]:
    """Registry entries for IN_NSE models (empty until models land in S9+)."""
    return []


def register_all(registry: ModelRegistry) -> None:
    """Register every IN_NSE model entry into a registry."""
    registry.register_all(entries())
