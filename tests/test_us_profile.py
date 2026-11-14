"""P9-S2: the US profile — null-rate policy, registry, formatting tokens.

NO numeric US rate exists anywhere in this project; every null raises the
typed error without the explicit flag."""

from __future__ import annotations

import pytest

# importing the module REGISTERS the profile (side effect by design)
import niveshdristi.markets.in_us.profile  # noqa: F401,E402


class TestUSProfile:
    def test_registered_second_market(self):
        from niveshdristi.markets.registry import get_registry

        registry = get_registry()
        us = registry.get("US_NYSE")
        assert us.market_id == "US_NYSE"
        assert us.currency == "USD"
        assert us.digit_grouping == "western"
        assert us.timezone == "America/New_York"
        assert us.session.open.hour == 9
        assert us.session.open.minute == 30
        assert us.session.close.hour == 16
        assert us.benchmark_symbol == ""  # benchmark UNAVAILABLE
        assert us.shorting_allowed is False  # project default: long-only

    def test_null_rate_without_flag_raises_typed_error_naming_field(self):
        from niveshdristi.markets.in_us.profile import (
            CostsNotModeledError,
            load_us_costs,
        )

        with pytest.raises(CostsNotModeledError, match="stt_delivery_sell_pct"):
            load_us_costs()  # no flag
        from niveshdristi.markets.in_us.profile import load_us_tax

        with pytest.raises(CostsNotModeledError, match="short_term_rate"):
            load_us_tax()  # no flag

    def test_with_flag_zero_fee_costs_and_banner_marker(self):
        from niveshdristi.markets.in_us.profile import (
            COSTS_NOT_MODELED_BANNER,
            COSTS_NOT_MODELED_CODE,
            us_market_rules,
        )

        costs = __import__(
            "niveshdristi.markets.in_us.profile", fromlist=["load_us_costs"]
        ).load_us_costs(costs_not_modeled=True)
        assert all(v == 0.0 for v in costs.values()), costs
        rules, marker = us_market_rules(costs_not_modeled=True)
        assert marker["banner"] == COSTS_NOT_MODELED_BANNER
        assert marker["limitation_code"] == COSTS_NOT_MODELED_CODE
        assert rules.rates.brokerage_per_order == 0.0

    def test_india_profile_unaffected(self):
        from niveshdristi.markets import IN_NSE_PROFILE
        from niveshdristi.markets.in_nse.loaders import load_costs

        data = load_costs()
        assert data["brokerage_per_order"] == 20.0  # still the India value
        assert IN_NSE_PROFILE.digit_grouping == "indian"
        assert IN_NSE_PROFILE.currency == "INR"

    def test_magnitude_checks_still_apply_to_non_null(self, tmp_path):
        """The strict loader's magnitude checks continue to apply to
        non-null values: point the strict loader at a US-shaped YAML with
        ONE non-null absurd rate (5.0 = 500%) and it must reject it."""
        from niveshdristi.core.errors import ConfigurationError
        from niveshdristi.markets.in_nse.loaders import load_costs

        bad = {
            "brokerage_per_order": 0.0, "stt_delivery_buy_pct": 0.0,
            "stt_delivery_sell_pct": 5.0,  # 500%: absurd, non-null
            "stt_intraday_sell_pct": 0.0, "exchange_charges_pct": 0.0001,
            "sebi_fees_pct": 0.000001, "stamp_duty_buy_pct": 0.0,
            "dp_charge_per_scrip": 0.0, "gst_pct": 0.0,
            "slippage_bps": 5,
        }
        import yaml as _yaml

        path = tmp_path / "costs_bad.yaml"
        path.write_text(_yaml.safe_dump(bad), encoding="utf-8")
        with pytest.raises(ConfigurationError, match="fails sanity"):
            load_costs(path)
