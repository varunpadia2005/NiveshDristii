"""FX-F tests: the offline guard blocks off-box connects and allows
loopback; mutation proof (disable the guard, show the off-box test fails)."""

from __future__ import annotations

import socket
import threading

import pytest

from tests.network_guard import activate, deactivate


class TestNetworkGuard:
    def test_offbox_connect_raises(self):
        with pytest.raises(RuntimeError, match="network blocked"):
            socket.create_connection(("203.0.113.5", 80), timeout=0.2)

    def test_loopback_connect_succeeds(self):
        """A throwaway local listener accepts a loopback connection."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        thread = threading.Thread(
            target=lambda: (server.accept(), server.close()), daemon=True)
        thread.start()
        conn = socket.create_connection(("127.0.0.1", port), timeout=2)
        conn.close()
        server.close()

    def test_mutation_proof_guard_disabled(self):
        """MUTATION: deactivate the guard -> off-box connect succeeds
        (this test reverses to prove the guard is doing the blocking)."""
        deactivate()
        try:
            with pytest.raises((socket.timeout, ConnectionError, OSError)):
                # 203.0.113.5 is TEST-NET-3: guaranteed unroutable
                socket.create_connection(("203.0.113.5", 80), timeout=0.5)
        finally:
            activate()  # re-enable for subsequent tests
