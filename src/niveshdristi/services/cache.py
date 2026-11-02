"""Services-level cache keys + cached fund payload (NEW, P8-S4).

st.cache_data with EXPLICIT keys: ledger tip hash + as_of + record count.
A cache hit performs ZERO recomputation (counter-tested). No blocking LLM
call ever happens here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_COUNT = {"calls": 0}


def ledger_cache_key(fund_id: str, base: str | Path | None = None) -> str:
    """Content key for the fund's current state: tip hash + last session +
    record count."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    ledger = PaperLedger(FundPaths(base).for_fund(fund_id).ledger)
    records = ledger.records()
    tip = records[-1]["hash"] if records else "empty"
    as_of = records[-1]["session_date"] if records else "none"
    basis = json.dumps([fund_id, str(base), tip, as_of, len(records)],
                       sort_keys=True)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def cached_read_fund(fund_id: str, base: str | Path | None, key: str) -> Any:
    """Cache-keyed read: callers MUST pass ledger_cache_key(...). The
    underlying read_fund runs at most once per key (counter-tested)."""
    import streamlit as st

    @st.cache_data(show_spinner=False)
    def _load(_fund_id: str, _base: str | Path | None, _key: str) -> Any:
        _COUNT["calls"] += 1
        from niveshdristi.services.fund import read_fund

        return read_fund(_fund_id, base=_base)

    return _load(fund_id, base, key)


def cached_call_count() -> int:
    """Test hook: how many times the underlying loader actually ran."""
    return _COUNT["calls"]


def reset_cached_call_count() -> None:
    _COUNT["calls"] = 0
