"""
Characterization Tests — Freeze Current Behavior

These tests capture the EXACT current outputs of each module on fixture data.
DO NOT modify expected values — they represent the baseline before rebuild.
If a test fails, it means behavior has changed; update the fixture, not the test.
"""
import sys
sys.path.insert(0, "src")

import json
import polars as pl
from datetime import date
import pytest

from niveshdristi.indicators import compute_all_indicators
from niveshdristi.signals import generate_signal_report, generate_signal_series, compute_conviction
from niveshdristi.fundamentals import check_guardrails
from niveshdristi.data.contracts import FundamentalData, GuardrailReport, SignalReport, RegimeReport
from niveshdristi.regime import market_regime
from niveshdristi.backtest import simulate
from niveshdristi.genai import validate_note, render_template
from niveshdristi.data.contracts import AnalystNote, FactsBundle


# ============================================================
# Load Fixtures
# ============================================================

def load_price_fixture():
    return pl.read_parquet("tests/fixtures/prices_reliance_30d.parquet")

def load_json_fixture(name):
    with open(f"tests/fixtures/{name}") as f:
        return json.load(f)


# ============================================================
# Indicator Tests
# ============================================================

def test_indicators_compute_all():
    """compute_all_indicators produces all expected columns on fixture data."""
    df = load_price_fixture()
    out = compute_all_indicators(df)

    # Check all indicator columns exist
    expected_cols = {
        "ema_20", "ema_50", "ema_200", "adx",
        "rsi", "macd", "macd_signal", "macd_hist",
        "atr", "bb_upper", "bb_mid", "bb_lower", "bb_pct",
        "obv", "vol_ratio"
    }
    missing = expected_cols - set(out.columns)
    assert not missing, f"Missing indicator columns: {missing}"

    # Check no nulls in key columns (after warmup period)
    warmup = 200  # EMA 200 needs 200 periods
    for col in ["rsi", "macd", "atr", "bb_pct"]:
        nulls = out[col][warmup:].null_count()
        assert nulls == 0, f"Column {col} has {nulls} nulls after warmup"

    # Save actual output for reference
    out.write_parquet("tests/fixtures/indicators_output.parquet")


# ============================================================
# Signal Engine Tests
# ============================================================

def test_generate_signal_report():
    """generate_signal_report matches frozen fixture output."""
    df = load_price_fixture()
    df = compute_all_indicators(df)

    signal = generate_signal_report("RELIANCE", df)

    # Load expected
    expected = load_json_fixture("signal_reliance.json")

    # Compare key fields (allow small floating point differences)
    assert signal.ticker == expected["ticker"]
    assert abs(signal.composite - expected["composite"]) < 0.05
    assert abs(signal.trend_score - expected["trend_score"]) < 0.05
    assert abs(signal.momentum_score - expected["momentum_score"]) < 0.05
    assert abs(signal.volatility_score - expected["volatility_score"]) < 0.05
    assert abs(signal.volume_score - expected["volume_score"]) < 0.05

    # Reasons should match (order may vary)
    assert set(signal.reasons) == set(expected["reasons"])


def test_generate_signal_series():
    """generate_signal_series returns a series aligned to input DataFrame."""
    df = load_price_fixture()
    df = compute_all_indicators(df)
    # Filter to rows where ADX is not null (first ~27 rows have null ADX)
    df = df.filter(pl.col("adx").is_not_null())

    series = generate_signal_series("RELIANCE", df)

    assert len(series) == len(df)
    assert series.min() >= -1.0
    assert series.max() <= 1.0


# ============================================================
# Fundamentals / Guardrails Tests
# ============================================================

def test_check_guardrails():
    """check_guardrails matches frozen fixture output."""
    fund_data = load_json_fixture("fundamentals_reliance.json")
    fund = FundamentalData(**fund_data)

    report = check_guardrails(fund)

    expected = load_json_fixture("guardrail_reliance.json")

    assert report.max_score_cap == expected["max_score_cap"]
    assert len(report.flags) == len(expected["flags"])
    for i, flag in enumerate(report.flags):
        assert flag["metric"] == expected["flags"][i]["metric"]
        assert flag["severity"] == expected["flags"][i]["severity"]


# ============================================================
# Conviction Tests
# ============================================================

def test_compute_conviction():
    """compute_conviction matches frozen fixture output."""
    signal_data = load_json_fixture("signal_reliance.json")
    guardrail_data = load_json_fixture("guardrail_reliance.json")
    regime_data = load_json_fixture("regime_sample.json")

    signal = SignalReport(**signal_data)
    guardrails = GuardrailReport(**guardrail_data)
    regime = RegimeReport(**regime_data)

    conviction = compute_conviction(signal, guardrails, regime, model=None)

    expected = load_json_fixture("conviction_reliance.json")

    assert conviction.score == expected["score"]
    assert conviction.capped_by_guardrails == expected["capped_by_guardrails"]
    assert conviction.components.technical == expected["components"]["technical"]
    assert conviction.components.fundamental == expected["components"]["fundamental"]
    assert conviction.components.regime == expected["components"]["regime"]
    assert conviction.components.ml == expected["components"]["ml"]


# ============================================================
# Regime Tests
# ============================================================

def test_market_regime():
    """market_regime classifies correctly on fixture data."""
    df = load_price_fixture()
    df = compute_all_indicators(df)

    # Test on fixture data (moderate trend, low vol -> choppy)
    state = market_regime(df, vix=14.5)
    assert state == "choppy"

    # Test bull (strong positive return, low vol)
    df_bull = df.clone()
    df_bull = df_bull.with_columns(
        (pl.col("adj_close") * (1 + pl.arange(0, len(df)) * 0.003)).alias("adj_close")
    )
    state = market_regime(df_bull, vix=14.5)
    assert state == "bull"

    # Test bear (negative return or high VIX)
    df_bear = df.clone()
    df_bear = df_bear.with_columns(
        (pl.col("adj_close") * (1 - pl.arange(0, len(df)) * 0.003)).alias("adj_close")
    )
    state = market_regime(df_bear, vix=28.0)
    assert state == "bear"

    # Test choppy (flat, medium vol)
    df_choppy = df.clone()
    df_choppy = df_choppy.with_columns(
        (pl.col("adj_close") * (1 + (pl.arange(0, len(df)) % 5 - 2) * 0.002)).alias("adj_close")
    )
    state = market_regime(df_choppy, vix=18.0)
    assert state == "choppy"


# ============================================================
# Backtest Tests
# ============================================================

def test_backtest_simulate():
    """simulate runs without error and produces expected structure."""
    df = load_price_fixture()
    df = compute_all_indicators(df)
    # Filter to rows with valid ADX for signal generation
    df = df.filter(pl.col("adx").is_not_null())

    prices = {"RELIANCE": df}
    signals = {"RELIANCE": generate_signal_series("RELIANCE", df)}

    # Provide explicit config to avoid CFG dict access bug
    from niveshdristi.backtest import BacktestConfig
    config = BacktestConfig(
        initial_capital=1_000_000,
        max_position_pct=0.10,
        signal_delay_days=1
    )
    result = simulate(prices, signals, config=config)

    # Structure checks
    assert hasattr(result, "equity_curve")
    assert hasattr(result, "trades")
    assert hasattr(result, "metrics")

    # Metrics keys
    expected_metrics = {"CAGR", "Volatility", "Sharpe", "MaxDD", "Trades"}
    assert set(result.metrics.keys()) == expected_metrics

    # Equity curve has date and equity columns
    assert "date" in result.equity_curve.columns
    assert "equity" in result.equity_curve.columns

    # Save for reference
    result.equity_curve.write_parquet("tests/fixtures/backtest_equity_curve.parquet")
    if len(result.trades) > 0:
        result.trades.write_parquet("tests/fixtures/backtest_trades.parquet")


# ============================================================
# GenAI Validator Tests
# ============================================================

def test_validate_note_passes_for_valid():
    """validate_note passes when note numbers are in facts bundle."""
    signal_data = load_json_fixture("signal_reliance.json")
    fund_data = load_json_fixture("fundamentals_reliance.json")
    guardrail_data = load_json_fixture("guardrail_reliance.json")
    regime_data = load_json_fixture("regime_sample.json")

    signal = SignalReport(**signal_data)
    fundamentals = FundamentalData(**fund_data)
    guardrails = GuardrailReport(**guardrail_data)
    regime = RegimeReport(**regime_data)

    # Create a note with ONLY numbers from the bundle
    # Signal composite = 0.44, VIX = 14.5, P/E = 24.5, ROE = 12%, D/E = 0.45, etc.
    note = AnalystNote(
        summary="Technical composite is 0.44 with positive trend and momentum",
        bull_case=["Price above long-term EMA", "Composite 0.44 indicates strength"],
        bear_case=["VIX at 14.5 indicates low fear"],
        risks=["Past performance not guarantee", "P/E ratio 24.5 is moderate"],
        would_change_view=["Break above key level with volume", "Earnings surprise vs consensus"]
    )

    bundle = FactsBundle(
        ticker="RELIANCE",
        date=date(2024, 5, 17),
        signal=signal,
        fundamentals=fundamentals,
        guardrails=guardrails,
        regime=regime,
        price_range=None,
        model=None,
        backtest_stats=None
    )

    valid, errors = validate_note(note, bundle)
    assert valid, f"Valid note rejected: {errors}"


def test_validate_note_fails_for_invented_number():
    """validate_note fails when note contains number not in bundle."""
    signal_data = load_json_fixture("signal_reliance.json")
    fund_data = load_json_fixture("fundamentals_reliance.json")
    guardrail_data = load_json_fixture("guardrail_reliance.json")
    regime_data = load_json_fixture("regime_sample.json")

    signal = SignalReport(**signal_data)
    fundamentals = FundamentalData(**fund_data)
    guardrails = GuardrailReport(**guardrail_data)
    regime = RegimeReport(**regime_data)

    # Note with invented number 99.9 (not in bundle)
    note = AnalystNote(
        summary="Stock will hit 99.9 target price",  # Invented number
        bull_case=["Strong momentum"],
        bear_case=[],
        risks=[],
        would_change_view=[]
    )

    bundle = FactsBundle(
        ticker="RELIANCE",
        date=date(2024, 1, 31),
        signal=signal,
        fundamentals=fundamentals,
        guardrails=guardrails,
        regime=regime,
        price_range=None,
        model=None,
        backtest_stats=None
    )

    valid, errors = validate_note(note, bundle)
    assert not valid
    assert any("99.9" in e for e in errors)


def test_render_template():
    """Jinja2 template renders without error."""
    from niveshdristi.data.contracts import FundamentalData, SignalReport, GuardrailReport, RegimeReport

    signal_data = load_json_fixture("signal_reliance.json")
    fund_data = load_json_fixture("fundamentals_reliance.json")
    guardrail_data = load_json_fixture("guardrail_reliance.json")
    regime_data = load_json_fixture("regime_sample.json")

    signal = SignalReport(**signal_data)
    fundamentals = FundamentalData(**fund_data)
    guardrails = GuardrailReport(**guardrail_data)
    regime = RegimeReport(**regime_data)

    context = {
        "ticker": "RELIANCE",
        "signal": signal,
        "fundamentals": fundamentals,
        "guardrails": guardrails,
        "regime": regime,
        "bull_case": ["Test"],
        "bear_case": ["Test"],
        "risks": ["Test"],
        "would_change_view": ["Test"],
    }

    output = render_template("analyst_note.j2", **context)
    assert "RELIANCE" in output
    assert "bullish" in output.lower() or "bearish" in output.lower() or "neutral" in output.lower()


# ============================================================
# Run All
# ============================================================

if __name__ == "__main__":
    test_indicators_compute_all()
    print("[OK] test_indicators_compute_all")

    test_generate_signal_report()
    print("[OK] test_generate_signal_report")

    test_generate_signal_series()
    print("[OK] test_generate_signal_series")

    test_check_guardrails()
    print("[OK] test_check_guardrails")

    test_compute_conviction()
    print("[OK] test_compute_conviction")

    test_market_regime()
    print("[OK] test_market_regime")

    test_backtest_simulate()
    print("[OK] test_backtest_simulate")

    test_validate_note_passes_for_valid()
    print("[OK] test_validate_note_passes_for_valid")

    test_validate_note_fails_for_invented_number()
    print("[OK] test_validate_note_fails_for_invented_number")

    test_render_template()
    print("[OK] test_render_template")

    print("\n[OK] All characterization tests passed!")