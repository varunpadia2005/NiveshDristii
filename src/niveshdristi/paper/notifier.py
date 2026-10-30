"""Notifier interface (NEW, Phase 6, amendment H).

A Protocol plus two implementations: NullNotifier (default, off) and
LogOnlyNotifier (writes to the events log via a callback). NO
Telegram/email/network code and NO secrets handling in Phase 6 — a real
notifier would implement Notifier and be registered by the caller
(composition point: cli/), behind the off-by-default flag.
"""

from __future__ import annotations

from typing import Any, Protocol

from niveshdristi.core.errors import ConfigurationError


class Notifier(Protocol):
    """Notification interface (amendment H): notify(event, payload)."""

    def notify(self, event: str, payload: dict[str, Any]) -> None:
        ...


class NullNotifier:
    """Default: off. Does nothing."""

    def notify(self, event: str, payload: dict[str, Any]) -> None:
        return None


class LogOnlyNotifier:
    """Log-only: delegates to a callback (e.g. the events log append)."""

    def __init__(self, sink: Any) -> None:
        if not callable(sink):
            raise ConfigurationError("LogOnlyNotifier sink must be callable")
        self._sink = sink

    def notify(self, event: str, payload: dict[str, Any]) -> None:
        self._sink(event, payload)


def default_notifier() -> Notifier:
    """The OFF-by-default notifier (amendment H)."""
    return NullNotifier()
