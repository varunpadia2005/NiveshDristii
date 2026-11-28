"""P21-NAMES S3 (NAMES-API-1-4): read-only view seam over the names
resolver so both UIs (Streamlit + web) share one implementation.

The UI import allowlist only permits services/paper/core/ui — so the
Streamlit resolver consumes THIS services module, which delegates to
niveshdristi.names.resolve.
"""

from __future__ import annotations


def load_names() -> dict[str, dict]:
    from niveshdristi.names.resolve import load_names as _load

    return _load()


def resolve(symbol: str) -> dict | None:
    from niveshdristi.names.resolve import resolve as _resolve

    return _resolve(symbol)


def search(q: str, limit: int = 20) -> list[dict]:
    from niveshdristi.names.resolve import search as _search

    return _search(q, limit=limit)
