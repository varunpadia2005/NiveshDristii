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
    cost_model=CostModel(
        # Brokerage (flat fee per order in INR)
        brokerage_per_order=20.0,  # # VERIFY: Typical discount broker
        brokerage_pct=0.0,
        # STT (Securities Transaction Tax) - on sell side for delivery
        stt_pct=0.001,  # 0.1% # VERIFY: Current STT rate
        # Exchange transaction charges
        exchange_charges_pct=0.0000345,  # 0.00345% # VERIFY: NSE circular
        # SEBI turnover fee
        sebi_fees_pct=0.000001,  # 0.0001% # VERIFY: SEBI circular
        # Stamp duty (on buy side)
        stamp_duty_pct=0.00015,  # 0.015% # VERIFY: Indian Stamp Act
        # GST on brokerage + exchange charges
        gst_pct=0.18,  # 18% # VERIFY: GST Council
        # Slippage (base)
        slippage_bps=5.0,  # 5 bps # VERIFY: Depends on liquidity
        # DP charge (per scrip on sell)
        dp_charge_per_scrip=13.5,  # ~13.5 INR # VERIFY: CDSL/NSDL
    ),
    tax_model=TaxModel(
        enabled=True,
        short_term_threshold_days=365,  # 12 months
        short_term_rate=0.20,  # 20% STCG # VERIFY: Finance Act
        long_term_rate=0.125,  # 12.5% LTCG # VERIFY: Finance Act
        long_term_exemption=1_25_000,  # 1.25 lakh exemption # VERIFY: Finance Act
        loss_setoff_years=8,
    ),
    shorting_allowed=False,  # Cash segment: no shorting for retail
    intraday_shorting_allowed=True,  # Intraday shorting allowed
    calendar_path=str(IN_NSE_BASE / "holidays_in.yaml"),
    default_universe="nifty50",
    benchmark_symbol="^NSEI",
    benchmark_is_total_return=True,  # Prefer Nifty 50 TRI
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
