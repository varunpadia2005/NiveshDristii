"""Ordered provider chain with fallback and retry (market-neutral).

Chain order comes from the ProviderRegistry (config-driven; no provider is
hard-assumed primary). A provider that is UNSUPPORTED for a kind
(NotImplementedError) or fails with an error is skipped in favour of the
next provider; each provider gets `retries` attempts. If every provider
fails, a typed ProviderError is raised — never an empty frame.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from niveshdristi.core.errors import ProviderError
from niveshdristi.marketdata.registry import ProviderRegistry


class ChainedDataClient:
    """Dispatch a DataClient method across an ordered provider chain."""

    def __init__(
        self,
        registry: ProviderRegistry,
        market_id: str,
        kind: str,
        *,
        retries: int = 1,
        retry_delay: float = 0.0,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.registry = registry
        self.market_id = market_id
        self.kind = kind
        self.retries = retries
        self.retry_delay = retry_delay
        self._sleep = sleeper or time.sleep

    def call(self, method: str, /, *args: Any, **kwargs: Any) -> Any:
        """Call `method` on the first provider in the chain that succeeds."""
        providers = self.registry.chain(self.market_id, self.kind)
        if not providers:
            raise ProviderError(
                f"no provider chain configured for ({self.market_id!r}, {self.kind!r})"
            )
        last_error: BaseException | None = None
        attempted: list[str] = []
        for provider in providers:
            for attempt in range(1, self.retries + 1):
                try:
                    return getattr(provider, method)(*args, **kwargs)
                except NotImplementedError:
                    # Unsupported for this kind — not an error, try next provider
                    attempted.append(f"{provider.provider_name}(unsupported)")
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - fallback is the point of the chain
                    last_error = exc
                    attempted.append(
                        f"{provider.provider_name}(attempt {attempt}: {type(exc).__name__})"
                    )
                    if attempt < self.retries and self.retry_delay:
                        self._sleep(self.retry_delay)
        raise ProviderError(
            f"all providers failed for {method!r} on "
            f"({self.market_id!r}, {self.kind!r}): {attempted}; "
            f"last error: {last_error!r}"
        )
