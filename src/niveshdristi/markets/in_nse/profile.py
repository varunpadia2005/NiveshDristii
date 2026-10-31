"""IN_NSE (NSE India) market profile — complete market definition for Indian equities."""

from datetime import time
from pathlib import Path

from niveshdristi.markets.registry import (
    CostModel,
    MarketProfile,
    PriceLimitConfig,
    SessionTimes,
    SettlementConfig,
    TaxModel,
    register_market,
)

# Base directory for IN_NSE market data
IN_NSE_BASE = Path(__file__).parent


def _build_cost_model() -> CostModel:
    """CostModel from costs.yaml (P4-S3: single source of truth; the values
    were previously hardcoded here and are pinned equal by tests)."""
    from niveshdristi.markets.in_nse.loaders import load_costs

    data = load_costs()
    return CostModel(
        brokerage_per_order=float(data["brokerage_per_order"]),
        brokerage_pct=0.0,
        stt_pct=float(data["stt_delivery_sell_pct"]),
        exchange_charges_pct=float(data["exchange_charges_pct"]),
        sebi_fees_pct=float(data["sebi_fees_pct"]),
        stamp_duty_pct=float(data["stamp_duty_buy_pct"]),
        gst_pct=float(data["gst_pct"]),
        slippage_bps=float(data["slippage_bps"]),
        dp_charge_per_scrip=float(data["dp_charge_per_scrip"]),
    )


def _build_tax_model() -> TaxModel:
    """TaxModel from tax.yaml (P4-S3)."""
    from niveshdristi.markets.in_nse.loaders import load_tax

    data = load_tax()
    return TaxModel(
        enabled=bool(data["enabled"]),
        short_term_threshold_days=int(data["short_term_threshold_days"]),
        short_term_rate=float(data["short_term_rate"]),
        long_term_rate=float(data["long_term_rate"]),
        long_term_exemption=float(data["long_term_exemption"]),
        loss_setoff_years=int(data["loss_setoff_years"]),
    )


IN_NSE_PROFILE = MarketProfile(
    market_id="IN_NSE",
    name="National Stock Exchange of India",
    timezone="Asia/Kolkata",
    currency="INR",
    session=SessionTimes(
        pre_open=time(9, 0),
        open=time(9, 15),
        close=time(15, 30),
        post_close=None,
    ),
    settlement=SettlementConfig(cycle="T+1", days=1),
    price_limits=PriceLimitConfig(
        enabled=True,
        default_bands=(0.02, 0.05, 0.10, 0.20),  # 2%, 5%, 10%, 20%
        index_bands=(0.10, 0.15, 0.20),
    ),
    cost_model=_build_cost_model(),
    tax_model=_build_tax_model(),
    shorting_allowed=False,  # Cash segment: no shorting for retail
    intraday_shorting_allowed=True,  # Intraday shorting allowed
    calendar_path=str(IN_NSE_BASE / "holidays_in.yaml"),
    default_universe="nifty50",
    benchmark_symbol="^NSEI",
    benchmark_is_total_return=True,  # Prefer Nifty 50 TRI
    # UNVERIFIED (2026-10-24): this symbol was NOT probed live in P0; fixture
    # use only — do not use for any live fetch until verified.
    volatility_index_symbol="^INDIAVIX",
    sector_taxonomy_path=str(IN_NSE_BASE / "sectors.yaml"),
    asm_gsm_path=str(IN_NSE_BASE / "asm_gsm.yaml"),
    fno_ban_path=str(IN_NSE_BASE / "fno_ban.yaml"),
    min_price=1.0,
    min_market_cap=0.0,  # 100 Cr minimum # VERIFY
    min_adv_crores=1.0,  # 1 Cr minimum ADV # VERIFY
    provider_suffixes={
        "yfinance": ".NS",
        "nse_bhavcopy": "",
        "nifty_indices": "",
    },
)


# Auto-register on import
register_market(IN_NSE_PROFILE)
