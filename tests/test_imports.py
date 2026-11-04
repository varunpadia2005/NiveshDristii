"""Basic import tests to verify module structure."""
import sys
sys.path.insert(0, "src")

def test_config():
    from niveshdristi.config import CFG
    assert CFG.data.provider == "yfinance"
    assert CFG.signals.weights["trend"] == 0.35
    print("✓ config")

def test_contracts():
    from niveshdristi.data.contracts import SignalReport, ValidationReport
    assert "composite" in SignalReport.__dataclass_fields__
    print("✓ contracts")

def test_providers():
    from niveshdristi.data.providers import YFinanceProvider, get_provider
    provider = get_provider("yfinance")
    assert isinstance(provider, YFinanceProvider)
    print("✓ providers")

def test_indicators():
    from niveshdristi.indicators import compute_all_indicators
    import polars as pl
    from datetime import date
    df = pl.DataFrame({
        "date": pl.date_range(date(2024,1,1), date(2024,1,10), "1d", eager=True),
        "open": [100]*10, "high": [101]*10, "low": [99]*10, "close": [100]*10,
        "volume": [1000]*10,
        "adj_open": [100]*10, "adj_high": [101]*10, "adj_low": [99]*10, "adj_close": [100]*10
    })
    out = compute_all_indicators(df)
    assert "rsi" in out.columns
    assert "macd" in out.columns
    assert "bb_upper" in out.columns
    print("✓ indicators")

def test_signals():
    from niveshdristi.signals import generate_signal_report
    import polars as pl
    from datetime import date
    df = pl.DataFrame({
        "date": pl.date_range(date(2024,1,1), date(2024,1,10), "1d", eager=True),
        "adj_open": [100]*10, "adj_high": [101]*10, "adj_low": [99]*10,
        "adj_close": [100]*10, "volume": [1000]*10,
        "ema_20": [100]*10, "ema_50": [99]*10, "ema_200": [98]*10,
        "rsi": [55]*10, "macd_hist": [0.5]*10, "bb_pct": [0.5]*10,
        "vol_ratio": [1.0]*10
    })
    sig = generate_signal_report("TEST", df)
    assert -1 <= sig.composite <= 1
    assert len(sig.reasons) >= 0
    print("✓ signals")

def test_genai_templates():
    from niveshdristi.genai.client import render_template
    out = render_template("analyst_note.j2",
        ticker="TEST", signal={"composite": 0.5, "components": {}},
        fundamentals={"pe_ratio": 20, "roe": 0.15, "debt_to_equity": 0.5},
        guardrails={"flags": [], "max_score_cap": 100},
        regime={"market_state": "bull", "vix_level": 15, "sector_quadrants": {}},
        bull_case=["Test"], bear_case=["Test"], risks=["Test"], would_change_view=["Test"]
    )
    assert "TEST" in out
    assert "bullish" in out
    print("✓ templates")

if __name__ == "__main__":
    test_config()
    test_contracts()
    test_providers()
    test_indicators()
    test_signals()
    test_genai_templates()
    print("\n✅ All import tests passed!")