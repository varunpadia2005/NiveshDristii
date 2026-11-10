"""Enforced offline guard (NEW, P10-S6 / FX-F).

Loaded via tests/conftest.py as an autouse session-scoped fixture.
Blocks any socket connect that leaves the machine (loopback allowed for
asyncio self-pipes and in-process test servers). DNS resolution is NOT
covered — a test that resolves a hostname but never connects is NOT
caught; the guard blocks the connect() syscall itself, not DNS.

A naive guard that blocks ALL sockets (including loopback) breaks the
five SectorRotation async tests because the Windows asyncio event loop
creates a loop-internal self-pipe via _fallback_socketpair.
"""

from __future__ import annotations

import socket
from typing import Any

_original_connect = socket.socket.connect
_original_create = socket.create_connection


def _is_loopback(address: object) -> bool:
    if isinstance(address, tuple) and len(address) >= 1:
        host = address[0]
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return True
    return False


def _guarded_connect(self: Any, address: Any) -> Any:
    if _is_loopback(address):
        return _original_connect(self, address)
    raise RuntimeError(
        f"network blocked: off-box connect to {address!r} "
        "(tests must be offline; see tests/network_guard.py)")


def _guarded_create(address: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_loopback(address):
        return _original_create(address, *args, **kwargs)
    raise RuntimeError(
        f"network blocked: off-box create_connection to {address!r} "
        "(tests must be offline; see tests/network_guard.py)")


def activate() -> None:
    """Install the guard (idempotent)."""
    socket.socket.connect = _guarded_connect  # type: ignore[assignment]
    socket.create_connection = _guarded_create  # type: ignore[assignment]


def deactivate() -> None:
    """Remove the guard (for cleanup)."""
    socket.socket.connect = _original_connect  # type: ignore[method-assign]
    socket.create_connection = _original_create  # type: ignore[method-assign]
