"""Model registry — catalog of ModelRegistryEntry metadata (neutral).

alpha/ must NOT import niveshdristi.markets (enforced by the import-boundary
test in tests/test_alpha.py). Market packs (e.g. markets/in_nse/models)
populate the registry from a composition point via register_all(registry).

CONVICTION SCALES ARE NOT COMPARABLE (plain statement): each model maps its
own raw statistic to [-1, +1] with its own UNVALIDATED DEFAULT constants.
Convictions across models are NOT calibrated and NOT probabilities; no
downstream combiner may treat them as such until Phase 4 introduces explicit
validation of the combination.
"""

from __future__ import annotations

from niveshdristi.core.alpha import ModelRegistryEntry
from niveshdristi.core.errors import ConfigurationError


class ModelRegistry:
    """Registry of alpha-model metadata with uniqueness and stub refusal."""

    def __init__(self) -> None:
        self._entries: dict[str, ModelRegistryEntry] = {}

    def register(self, entry: ModelRegistryEntry) -> None:
        """Register an entry; duplicate model_id is a ConfigurationError."""
        if entry.model_id in self._entries:
            raise ConfigurationError(f"duplicate model_id: {entry.model_id!r}")
        self._entries[entry.model_id] = entry

    def register_all(self, entries: list[ModelRegistryEntry]) -> None:
        for entry in entries:
            self.register(entry)

    def entries(self) -> tuple[ModelRegistryEntry, ...]:
        """All registered entries, ordered by model_id."""
        return tuple(self._entries[k] for k in sorted(self._entries))

    def entry_for(self, model_id: str) -> ModelRegistryEntry:
        """Look up one entry; unknown id is a ConfigurationError."""
        try:
            return self._entries[model_id]
        except KeyError:
            raise ConfigurationError(f"unknown model_id: {model_id!r}") from None

    def live_entries(self) -> tuple[ModelRegistryEntry, ...]:
        """Entries whose data_status is 'live' (stubs excluded, no error)."""
        return tuple(e for e in self.entries() if e.data_status == "live")

    def require_live(
        self, entry: ModelRegistryEntry, *, allow_stub: bool = False
    ) -> ModelRegistryEntry:
        """Refuse stub/unavailable models for live use unless explicitly allowed."""
        if entry.data_status != "live" and not allow_stub:
            raise ConfigurationError(
                f"model {entry.model_id!r} has data_status={entry.data_status!r}; "
                "refusing live use (pass allow_stub=True to override)"
            )
        return entry

