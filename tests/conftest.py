"""Shared test fixtures (NEW, P10-S6 / FX-F)."""

from __future__ import annotations

import pytest

from tests.network_guard import activate, deactivate


@pytest.fixture(autouse=True, scope="session")
def _enforce_offline():
    """FX-F: make 'no network in tests' an ENFORCED property.

    Blocks off-box socket connects for the entire test session. Loopback
    is allowed (asyncio self-pipes, in-process servers). DNS resolution is
    NOT covered — the guard blocks the connect() syscall, not DNS.
    A naive all-socket guard breaks the five SectorRotation async tests
    unless loopback is allowed."""
    activate()
    yield
    deactivate()
