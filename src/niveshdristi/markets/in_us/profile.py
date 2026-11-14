"""US_NYSE market profile (NEW, P9-S2).

Global-readiness proof: a SECOND market profile that registers alongside
IN_NSE and runs the SAME engine with ZERO core/engine edits. EVERY US cost
and tax rate is NULL (see costs.yaml / tax.yaml — no invented rates, no
verified source); composing engine-ready MarketRules from this profile
REQUIRES costs_not_modeled=True, and the result carries the
"COSTS NOT MODELED" banner and the costs_not_modeled limitation code.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from niveshdristi.core.errors import ConfigurationError
from niveshdristi.markets.registry import (
    CostModel,
    MarketProfile,
    PriceLimitConfig,
    SessionTimes,
    SettlementConfig,
    register_market,
    to_rules,
)

IN_US_BASE = Path(__file__).resolve().parent

# The NULL rate fields (every rate in costs.yaml / tax.yaml)
NULL_RATE_FIELDS: tuple[str, ...] = (
    "brokerage_per_order", "brokerage_pct", "stt_delivery_buy_pct",
    "stt_delivery_sell_pct", "stt_intraday_sell_pct", "exchange_charges_pct",
    "sebi_fees_pct", "stamp_duty_buy_pct", "dp_charge_per_scrip", "gst_pct",
    "transaction_levy", "slippage_base_bps", "enabled",
    "short_term_threshold_days", "short_term_rate", "long_term_rate",
    "long_term_exemption", "loss_setoff_years",
)

COSTS_NOT_MODELED_BANNER = "COSTS NOT MODELED"
COSTS_NOT_MODELED_CODE = "costs_not_modeled"


class CostsNotModeledError(ConfigurationError):
    """Composing US MarketRules without the explicit costs_not_modeled flag
    (the YAML rates are NULL — no numeric US rate exists in this project)."""


def _load_null_yaml(name: str) -> dict:
    """Parse the US YAML; return {field: value-or-None}."""
    data = yaml.safe_load((IN_US_BASE / name).read_text(encoding="utf-8")) or {}
    return data


def load_us_costs(*, costs_not_modeled: bool = False) -> dict[str, float]:
    """US cost rates. NULLs map to 'rate not modeled': WITHOUT the flag this
    raises CostsNotModeledError naming the null fields; WITH it every null
    becomes 0.0 (zero-fee costs) and the caller MUST surface the banner."""
    data = _load_null_yaml("costs.yaml")
    nulls = [k for k, v in sorted(data.items()) if v is None]
    if nulls and not costs_not_modeled:
        raise CostsNotModeledError(
            "US cost rates are not modeled (null in costs.yaml): "
            f"{nulls}; pass costs_not_modeled=True to proceed with "
            "zero-fee costs and the COSTS NOT MODELED banner"
        )
    return {k: (0.0 if v is None else float(v)) for k, v in sorted(data.items())}


def load_us_tax(*, costs_not_modeled: bool = False) -> dict[str, float | int | bool]:
    """US tax rates — same null policy as costs."""
    data = _load_null_yaml("tax.yaml")
    nulls = [k for k, v in sorted(data.items()) if v is None]
    if nulls and not costs_not_modeled:
        raise CostsNotModeledError(
            "US tax rates are not modeled (null in tax.yaml): "
            f"{nulls}; pass costs_not_modeled=True to proceed"
        )
    return {k: (0 if v is None else v) for k, v in sorted(data.items())}


# The profile: built FRESH (not inherited from IN_NSE — inheriting would
# silently carry India's cost numbers). cost_model holds the NULL-YAML
# zeros (only reachable with costs_not_modeled=True); tax_model is None
# (tax not modeled). The authoritative US rates are the NULL YAML files.

_us_costs = load_us_costs(costs_not_modeled=True)  # nulls -> 0.0

US_NYSE_PROFILE = MarketProfile(
    market_id="US_NYSE",
    name="New York Stock Exchange",
    timezone="America/New_York",
    currency="USD",
    digit_grouping="western",  # 3-3-3 grouping
    compact_units=(("billion", 1_000_000_000), ("million", 1_000_000),
                   ("thousand", 1_000)),
    session=SessionTimes(pre_open=None,
                         open=__import__("datetime").time(9, 30),
                         close=__import__("datetime").time(16, 0),
                         post_close=None),
    settlement=SettlementConfig(cycle="T+1", days=1),
    price_limits=PriceLimitConfig(enabled=False),  # no verified US bands
    cost_model=CostModel(
        brokerage_per_order=_us_costs["brokerage_per_order"],
        stt_pct=_us_costs["stt_delivery_sell_pct"],
        exchange_charges_pct=_us_costs["exchange_charges_pct"],
        sebi_fees_pct=_us_costs["sebi_fees_pct"],
        stamp_duty_pct=_us_costs["stamp_duty_buy_pct"],
        gst_pct=_us_costs["gst_pct"],
        dp_charge_per_scrip=_us_costs["dp_charge_per_scrip"],
        slippage_bps=_us_costs["slippage_base_bps"],
    ),
    tax_model=None,  # tax NOT modeled: tax.yaml is all-null
    benchmark_symbol="",   # UNAVAILABLE: no verified US benchmark source
    benchmark_is_total_return=False,
    calendar_path=str(IN_US_BASE / "holidays_us.yaml"),  # EMPTY: no invented
    shorting_allowed=False,  # project default is long-only (profile field)
    intraday_shorting_allowed=False,
)

register_market(US_NYSE_PROFILE)


def us_market_rules(*, costs_not_modeled: bool = False):
    """MarketRules for the US profile. REFUSES to produce a cost number from
    a null rate without the explicit flag; WITH the flag every rate is 0.0
    and the caller must attach the COSTS NOT MODELED banner. Since P10-S2
    the costs_not_modeled LIMITATION CODE is first-class in
    core/limitations.py and is expected in every US limitation set (the
    marker documents it; the caller attaches it to the DataLimitations)."""
    load_us_costs(costs_not_modeled=costs_not_modeled)  # may raise
    load_us_tax(costs_not_modeled=costs_not_modeled)
    rules = to_rules(US_NYSE_PROFILE)
    return rules, {
        "banner": COSTS_NOT_MODELED_BANNER if costs_not_modeled else None,
        "limitation_code": (COSTS_NOT_MODELED_CODE if costs_not_modeled
                            else None),
    }
