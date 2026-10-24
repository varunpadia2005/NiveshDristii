"""Strict loaders for the IN_NSE costs/tax YAMLs (NEW, P4-S3).

Rules:
- Unknown keys are REJECTED (ConfigurationError), like
  config_loader._validate_no_unknown_keys.
- Magnitude sanity: fee FRACTIONS must satisfy 0 < rate < 0.05, gst < 1,
  slippage in bps (> 0), tax rates in [0, 1]. A percent-style value (e.g.
  0.1 for a fraction field) fails loudly — the 100x misreading hazard from
  the units audit is guarded here.
- verified=true requires non-empty source AND verified_on (mirrors the
  core.market_rules validator).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from niveshdristi.core.errors import ConfigurationError

_ALLOWED_COST_KEYS = {
    "brokerage_per_order", "stt_delivery_buy_pct", "stt_delivery_sell_pct",
    "stt_intraday_sell_pct", "exchange_charges_pct", "sebi_fees_pct",
    "stamp_duty_buy_pct", "gst_pct", "slippage_bps", "dp_charge_per_scrip",
    "verified", "source", "verified_on",
}
_FRACTION_COST_KEYS = (
    "stt_delivery_buy_pct", "stt_delivery_sell_pct", "exchange_charges_pct",
    "sebi_fees_pct", "stamp_duty_buy_pct",
)
_MAX_FEE_FRACTION = 0.05  # sanity ceiling: no fee fraction legitimately exceeds 5%

_ALLOWED_TAX_KEYS = {
    "enabled", "short_term_threshold_days", "holding_period_months",
    "short_term_rate", "long_term_rate", "long_term_exemption",
    "loss_setoff_years", "indexation_benefit",
    "verified", "source", "verified_on",
}


def _load_yaml(path: Path, allowed: set[str], kind: str) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"{kind} file missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigurationError(f"{kind} file is not a mapping: {path}")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigurationError(f"{kind}: unknown keys: {unknown}")
    return data


def _check_verified(data: dict[str, Any], kind: str) -> None:
    if data.get("verified") is True:
        source = str(data.get("source", "") or "")
        verified_on = data.get("verified_on")
        has_date = isinstance(verified_on, (date, datetime)) or (
            isinstance(verified_on, str) and len(verified_on) >= 10
        )
        if not source.strip() or not has_date:
            raise ConfigurationError(
                f"{kind}: verified=true requires non-empty source and verified_on"
            )


def load_costs(path: Path | None = None) -> dict[str, Any]:
    """Load and validate costs.yaml (strict)."""
    path = path or Path(__file__).parent / "costs.yaml"
    data = _load_yaml(path, _ALLOWED_COST_KEYS, "costs")
    for key in _FRACTION_COST_KEYS:
        value = data.get(key)
        if value is None or not (0 < float(value) < _MAX_FEE_FRACTION):
            raise ConfigurationError(
                f"costs: {key}={value!r} fails sanity (0 < fraction < "
                f"{_MAX_FEE_FRACTION}); percent-style values are rejected"
            )
    gst = data.get("gst_pct")
    if gst is None or not (0 <= float(gst) < 1):
        raise ConfigurationError(f"costs: gst_pct={gst!r} fails sanity (0 <= gst < 1)")
    slip = data.get("slippage_bps")
    if slip is None or not (0 <= float(slip) < 1000):
        raise ConfigurationError(f"costs: slippage_bps={slip!r} fails sanity (bps)")
    _check_verified(data, "costs")
    return data


def load_tax(path: Path | None = None) -> dict[str, Any]:
    """Load and validate tax.yaml (strict)."""
    path = path or Path(__file__).parent / "tax.yaml"
    data = _load_yaml(path, _ALLOWED_TAX_KEYS, "tax")
    for key in ("short_term_rate", "long_term_rate"):
        value = data.get(key)
        if value is None or not (0 <= float(value) <= 1):
            raise ConfigurationError(f"tax: {key}={value!r} fails sanity (0..1)")
    months = data.get("holding_period_months")
    if months is None or not (1 <= int(months) <= 1200):
        raise ConfigurationError(f"tax: holding_period_months={months!r} fails sanity")
    _check_verified(data, "tax")
    return data
