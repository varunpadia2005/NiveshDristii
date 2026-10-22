# Characterization Test Fixtures
# These are synthetic but realistic data to freeze current behavior

import polars as pl
from datetime import date, timedelta
import json

# 1. Price fixture: 100+ trading days of synthetic OHLCV for RELIANCE
def create_price_fixture():
    base_date = date(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(180)]
    # Skip weekends
    dates = [d for d in dates if d.weekday() < 5][:100]  # ~100 trading days

    # Trending up with some noise
    base_price = 2500.0
    prices = []
    for i, d in enumerate(dates):
        trend = i * 2.5
        noise = (i % 7 - 3) * 5
        close = base_price + trend + noise
        high = close + 15
        low = close - 15
        open_ = close + (i % 5 - 2) * 3
        volume = 1_000_000 + (i % 10) * 100_000
        prices.append({
            "date": d,
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": volume,
            "adj_open": round(open_, 2),
            "adj_high": round(high, 2),
            "adj_low": round(low, 2),
            "adj_close": round(close, 2),
        })
    return pl.DataFrame(prices)

# 2. Fundamentals fixture
fundamentals_fixture = {
    "ticker": "RELIANCE",
    "pe_ratio": 24.5,
    "pb_ratio": 2.1,
    "roe": 0.12,
    "debt_to_equity": 0.45,
    "profit_margin": 0.08,
    "revenue_growth": 0.15,
    "sector": "Energy",
    "as_of": "2024-01-15"
}

# 3. Signal report fixture (expected output from generate_signal_report)
signal_fixture = {
    "ticker": "RELIANCE",
    "date": "2024-05-17",
    "trend_score": 1.0,
    "momentum_score": 0.5,
    "volatility_score": -0.399,
    "volume_score": 0.0,
    "composite": 0.44,
    "components": {
        "trend": 1.0,
        "momentum": 0.5,
        "volatility": -0.399,
        "volume": 0.0
    },
    "reasons": [
        "Price above 200-day EMA"
    ]
}

# 4. Guardrail report fixture
guardrail_fixture = {
    "flags": [],
    "max_score_cap": 100
}

# 5. Regime report fixture
regime_fixture = {
    "market_state": "bull",
    "vix_level": 14.5,
    "sector_quadrants": {
        "IT": "Leading",
        "Bank": "Weakening",
        "Auto": "Improving",
        "Pharma": "Lagging",
        "FMCG": "Leading",
        "Metal": "Improving",
        "Energy": "Leading",
        "Infra": "Weakening"
    },
    "state_probs": {}
}

# 6. Conviction score fixture (expected output from compute_conviction)
conviction_fixture = {
    "score": 75,
    "components": {
        "technical": 72,
        "fundamental": 100,
        "regime": 80,
        "ml": 50
    },
    "capped_by_guardrails": False,
    "details": {
        "weights": {
            "technical": 0.30,
            "fundamental": 0.25,
            "regime": 0.20,
            "ml": 0.25
        },
        "raw_score": 74.6,
        "guardrail_cap": 100
    }
}

# Save all fixtures
if __name__ == "__main__":
    import os
    os.makedirs("tests/fixtures", exist_ok=True)

    # Price fixture as Parquet
    price_df = create_price_fixture()
    price_df.write_parquet("tests/fixtures/prices_reliance_30d.parquet")

    # JSON fixtures
    fixtures = {
        "fundamentals_reliance.json": fundamentals_fixture,
        "signal_reliance.json": signal_fixture,
        "guardrail_reliance.json": guardrail_fixture,
        "regime_sample.json": regime_fixture,
        "conviction_reliance.json": conviction_fixture,
    }

    for fname, data in fixtures.items():
        with open(f"tests/fixtures/{fname}", "w") as f:
            json.dump(data, f, indent=2)

    print("[OK] Fixtures created in tests/fixtures/")
    print(f"  - prices_reliance_30d.parquet ({len(price_df)} rows)")
    for fname in fixtures:
        print(f"  - {fname}")