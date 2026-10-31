"""Provider registry — ordered provider chains per (market_id, data kind).

Chain ORDER is data-driven: callers register an ordered list of provider
names per kind; no provider is hard-assumed primary (the IN_NSE default for
prices is yfinance, with bhavcopy files used for delivery enrichment).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.marketdata.client import DATA_KINDS, DataClient

# A factory builds a DataClient; adapters are constructed per market
ProviderFactory = Callable[[], DataClient]


class ProviderRegistry:
    """Registry of provider factories and ordered chains per market/kind."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}
        self._chains: dict[tuple[str, str], list[str]] = {}

    def register_factory(self, name: str, factory: ProviderFactory) -> None:
        """Register (or replace) a provider factory by name."""
        self._factories[name] = factory

    def set_chain(self, market_id: str, kind: str, provider_names: Sequence[str]) -> None:
        """Set the ordered provider chain for (market_id, kind)."""
        if kind not in DATA_KINDS:
            raise ConfigurationError(f"unknown data kind: {kind!r}")
        unknown = [p for p in provider_names if p not in self._factories]
        if unknown:
            raise ConfigurationError(f"chain references unregistered providers: {unknown}")
        self._chains[(market_id, kind)] = list(provider_names)

    def chain(self, market_id: str, kind: str) -> list[DataClient]:
        """Materialize the ordered provider chain; empty if none configured."""
        names = self._chains.get((market_id, kind), [])
        return [self._factories[n]() for n in names]

    def chain_names(self, market_id: str, kind: str) -> list[str]:
        """Ordered provider names for (market_id, kind) without building."""
        return list(self._chains.get((market_id, kind), []))


def default_registry(
    chains: Mapping[tuple[str, str], Sequence[str]],
    factories: Mapping[str, ProviderFactory],
) -> ProviderRegistry:
    """Build a registry from plain dicts (used by config wiring and tests)."""
    reg = ProviderRegistry()
    for name, factory in factories.items():
        reg.register_factory(name, factory)
    for (market_id, kind), providers in chains.items():
        reg.set_chain(market_id, kind, providers)
    return reg
