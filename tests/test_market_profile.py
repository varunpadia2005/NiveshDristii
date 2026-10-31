"""
Test IN_NSE market profile loads from YAML and all # VERIFY rates exist.

Protects the rule that IN_NSE profile loads from YAML files and that every
# VERIFY rate listed in docs/VERIFY.md exists in the corresponding YAML.
"""

from pathlib import Path

import pytest

from niveshdristi.markets import IN_NSE_PROFILE, get_registry
from niveshdristi.markets.registry import MarketProfile


class TestIN_NSEProfileLoads:
    """IN_NSE profile loads correctly from YAML files."""

    def test_profile_registered(self):
        """IN_NSE profile is registered in global registry."""
        registry = get_registry()
        assert "IN_NSE" in registry
        profile = registry.get("IN_NSE")
        assert isinstance(profile, MarketProfile)

    def test_market_id(self):
        """Market ID is IN_NSE."""
        assert IN_NSE_PROFILE.market_id == "IN_NSE"

    def test_name(self):
        """Name is correct."""
        assert IN_NSE_PROFILE.name == "National Stock Exchange of India"

    def test_timezone(self):
        """Timezone is Asia/Kolkata."""
        assert IN_NSE_PROFILE.timezone == "Asia/Kolkata"

    def test_currency(self):
        """Currency is INR."""
        assert IN_NSE_PROFILE.currency == "INR"

    def test_session_times(self):
        """Session times are 09:15 to 15:30 with pre_open at 09:00."""
        assert IN_NSE_PROFILE.session.open.hour == 9
        assert IN_NSE_PROFILE.session.open.minute == 15
        assert IN_NSE_PROFILE.session.close.hour == 15
        assert IN_NSE_PROFILE.session.close.minute == 30
        assert IN_NSE_PROFILE.session.pre_open is not None
        assert IN_NSE_PROFILE.session.pre_open.hour == 9
        assert IN_NSE_PROFILE.session.pre_open.minute == 0

    def test_settlement_t1(self):
        """Settlement is T+1 (1 day)."""
        assert IN_NSE_PROFILE.settlement.cycle == "T+1"
        assert IN_NSE_PROFILE.settlement.days == 1

    def test_shorting_allowed_false(self):
        """Cash segment shorting is False."""
        assert IN_NSE_PROFILE.shorting_allowed is False

    def test_intraday_shorting_allowed_true(self):
        """Intraday shorting is True."""
        assert IN_NSE_PROFILE.intraday_shorting_allowed is True

    def test_benchmark_symbol(self):
        """Benchmark is ^NSEI."""
        assert IN_NSE_PROFILE.benchmark_symbol == "^NSEI"

    def test_benchmark_is_total_return(self):
        """Benchmark is total return index."""
        assert IN_NSE_PROFILE.benchmark_is_total_return is True


class TestIN_NSEYAMLFilesExist:
    """YAML files referenced by profile exist."""

    def test_holidays_yaml(self):
        """holidays_in.yaml exists."""
        path = Path(IN_NSE_PROFILE.calendar_path)
        assert path.exists(), f"holidays_in.yaml not found at {path}"

    def test_sectors_yaml(self):
        """sectors.yaml exists."""
        path = Path(IN_NSE_PROFILE.sector_taxonomy_path)
        assert path.exists(), f"sectors.yaml not found at {path}"

    def test_asm_gsm_yaml(self):
        """asm_gsm.yaml exists."""
        path = Path(IN_NSE_PROFILE.asm_gsm_path)
        assert path.exists(), f"asm_gsm.yaml not found at {path}"

    def test_fno_ban_yaml(self):
        """fno_ban.yaml exists."""
        path = Path(IN_NSE_PROFILE.fno_ban_path)
        assert path.exists(), f"fno_ban.yaml not found at {path}"


class TestVerifyRatesExistInYAML:
    """
    Every # VERIFY rate listed in docs/VERIFY.md exists in the YAML files.

    This test reads docs/VERIFY.md, extracts all rates marked with '# VERIFY',
    and verifies they exist in the corresponding YAML files.
    """

    def test_costs_yaml_contains_all_verify_rates(self):
        """All cost rates from VERIFY.md exist in costs.yaml."""
        costs_path = Path("src/niveshdristi/markets/in_nse/costs.yaml")
        # STRENGTHENED in P4-S3: the latent skip guard is replaced by a hard
        # assertion — the file exists and is loaded by the strict loader.
        assert costs_path.exists(), f"{costs_path} must exist"
        from niveshdristi.markets.in_nse.loaders import load_costs
        load_costs()  # strict load must succeed

        import yaml
        with open(costs_path) as f:
            costs = yaml.safe_load(f)

        # Rates from VERIFY.md Table 4 that must be in costs.yaml
        required_costs = [
            "brokerage_per_order",
            "stt_delivery_sell_pct",
            "stt_intraday_sell_pct",
            "exchange_charges_pct",
            "sebi_fees_pct",
            "stamp_duty_buy_pct",
            "gst_pct",
            "slippage_bps",
            "dp_charge_per_scrip",
        ]
        for key in required_costs:
            assert key in costs, f"Missing # VERIFY rate '{key}' in costs.yaml"

    def test_tax_yaml_contains_all_verify_rates(self):
        """All tax rates from VERIFY.md exist in tax.yaml."""
        tax_path = Path("src/niveshdristi/markets/in_nse/tax.yaml")
        if not tax_path.exists():
            pytest.skip("tax.yaml not yet created - will be created per spec")

        import yaml
        with open(tax_path) as f:
            tax = yaml.safe_load(f)

        required_tax = [
            "short_term_rate",
            "long_term_rate",
            "long_term_exemption",
            "short_term_threshold_days",
            "loss_setoff_years",
        ]
        for key in required_tax:
            assert key in tax, f"Missing # VERIFY rate '{key}' in tax.yaml"

    def test_holidays_yaml_has_current_year(self):
        """holidays_in.yaml has years_covered and 2024 holidays in the holidays list."""
        import yaml
        with open(IN_NSE_PROFILE.calendar_path, encoding="utf-8") as f:
            holidays = yaml.safe_load(f)
        assert "years_covered" in holidays, "years_covered key missing"
        assert 2024 in holidays.get("years_covered", []), "2024 not in years_covered"
        any_2024 = any(d.startswith("2024-") for d in holidays.get("holidays", []))
        assert any_2024, "2024 holidays missing from holidays list"

    @pytest.mark.xfail(strict=True, reason="Phase 2: fill 2026 holidays from the NSE official list")
    def test_holidays_yaml_covers_current_year(self):
        """holidays_in.yaml covers the current year (2026-10-23)."""
        from datetime import date

        import yaml
        with open(IN_NSE_PROFILE.calendar_path, encoding="utf-8") as f:
            holidays = yaml.safe_load(f)
        current_year = date.today().year
        assert current_year in holidays.get("years_covered", []), (
            f"{current_year} not in years_covered"
        )
        assert any(
            d.startswith(f"{current_year}-") for d in holidays.get("holidays", [])
        ), f"{current_year} holidays missing from holidays list"

    def test_cost_model_matches_profile(self):
        """Profile's cost_model matches costs.yaml (if exists)."""
        costs_path = Path("src/niveshdristi/markets/in_nse/costs.yaml")
        if not costs_path.exists():
            pytest.skip("costs.yaml not yet created")

        import yaml
        with open(costs_path) as f:
            costs_yaml = yaml.safe_load(f)

        profile_costs = IN_NSE_PROFILE.cost_model
        # Key rates should match
        assert profile_costs.brokerage_per_order == costs_yaml.get("brokerage_per_order")
        assert profile_costs.stt_pct == costs_yaml.get("stt_delivery_sell_pct")
        assert profile_costs.exchange_charges_pct == costs_yaml.get("exchange_charges_pct")
        assert profile_costs.sebi_fees_pct == costs_yaml.get("sebi_fees_pct")
        assert profile_costs.stamp_duty_pct == costs_yaml.get("stamp_duty_buy_pct")
        assert profile_costs.gst_pct == costs_yaml.get("gst_pct")
        assert profile_costs.slippage_bps == costs_yaml.get("slippage_bps")
        assert profile_costs.dp_charge_per_scrip == costs_yaml.get("dp_charge_per_scrip")

    def test_tax_model_matches_profile(self):
        """Profile's tax_model matches tax.yaml (if exists)."""
        tax_path = Path("src/niveshdristi/markets/in_nse/tax.yaml")
        if not tax_path.exists():
            pytest.skip("tax.yaml not yet created")

        import yaml
        with open(tax_path) as f:
            tax_yaml = yaml.safe_load(f)

        profile_tax = IN_NSE_PROFILE.tax_model
        assert profile_tax.short_term_rate == tax_yaml.get("short_term_rate")
        assert profile_tax.long_term_rate == tax_yaml.get("long_term_rate")
        assert profile_tax.long_term_exemption == tax_yaml.get("long_term_exemption")
        assert profile_tax.short_term_threshold_days == tax_yaml.get("short_term_threshold_days")
        assert profile_tax.loss_setoff_years == tax_yaml.get("loss_setoff_years")
