"""P21-NAMES: thin re-export — the implementation lives in
services/names_view.py (the UI import boundary only allows services/
paper/core/ui, so the single resolver lives there)."""

from niveshdristi.services.names_view import (
    load_names,
    resolve,
    search,
)

__all__ = ["load_names", "resolve", "search"]
