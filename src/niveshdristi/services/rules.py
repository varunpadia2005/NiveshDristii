"""Market-rules composition from the fund header (NEW, P9-S1).

services reads the market_id and MarketRules from the LEDGER HEADER
(market_rules_digest) — never a hard-coded market id."""

from __future__ import annotations

import json
from pathlib import Path

from niveshdristi.core.market_rules import MarketRules


def rules_from_header(fund_id: str, base: str | Path | None = None) -> MarketRules:
    """Reconstruct the fund's MarketRules from its ledger header digest."""
    from niveshdristi.paper.fund import FundPaths
    from niveshdristi.paper.ledger import PaperLedger

    header = PaperLedger(FundPaths(base).for_fund(fund_id).ledger).header()
    return MarketRules.model_validate(json.loads(header["market_rules_digest"]))


def market_id_from_header(fund_id: str, base: str | Path | None = None) -> str:
    return rules_from_header(fund_id, base).market_id
