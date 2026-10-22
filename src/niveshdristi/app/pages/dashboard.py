"""Dashboard page: Market overview with Groww-inspired design."""
import streamlit as st
import pandas as pd
from niveshdristi.config import CFG
from niveshdristi.app.components import (
    page_header, render_disclaimer, metric_card, quick_stats_row,
    stock_card, signal_breakdown_chart, regime_indicator,
    sector_quadrant_chart, empty_state, loading_skeleton
)


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()

    # Page header
    page_header("Dashboard", "Market overview and quick signals", "📊")

    # Load universe
    universe = api_get("/universe/default")
    if not universe:
        empty_state("📭", "No Data", "Unable to load universe")
        return

    tickers = universe.get("tickers", [])

    # Market breadth stats
    bullish = bearish = neutral = 0
    signals_data = {}

    # Fetch all signals (show loading)
    with st.spinner("Loading market signals..."):
        for t in tickers:
            sig = api_get(f"/signal/{t}")
            if sig and "composite" in sig:
                signals_data[t] = sig
                if sig["composite"] > 0.2:
                    bullish += 1
                elif sig["composite"] < -0.2:
                    bearish += 1
                else:
                    neutral += 1

    # Market breadth row
    st.markdown("### Market Breadth")
    stats = [
        {"label": "Total Stocks", "value": str(len(tickers)), "icon": "📈"},
        {"label": "Bullish", "value": str(bullish), "change": f"+{bullish}", "change_type": "positive", "icon": "🟢"},
        {"label": "Bearish", "value": str(bearish), "change": f"-{bearish}", "change_type": "negative", "icon": "🔴"},
        {"label": "Neutral", "value": str(neutral), "change_type": "neutral", "icon": "🟡"},
    ]
    quick_stats_row(stats)
    st.markdown("<br>", unsafe_allow_html=True)

    # Regime indicator
    st.markdown("### Market Regime")
    regime = api_get("/regime")
    if regime:
        from niveshdristi.app.components import regime_indicator
        regime_indicator(regime.get("market_state", "unknown"), regime.get("vix_level", 15))

    st.markdown("<br>", unsafe_allow_html=True)

    # Sector quadrants
    if regime and regime.get("sectors"):
        st.markdown("### Sector Rotation (RRG)")
        from niveshdristi.app.components import sector_quadrant_chart
        st.plotly_chart(sector_quadrant_chart(regime["sectors"]), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Signal overview table
    st.markdown("### Signal Overview")

    # Build table data
    rows = []
    for t in tickers:
        sig = api_get(f"/signal/{t}")
        px = api_get(f"/price/{t}")
        if sig:
            rows.append({
                "Symbol": t,
                "Price": f"₹{px.get('last_price', 0):,.1f}" if px else "N/A",
                "Signal": sig.get("composite", 0),
                "Trend": sig.get("trend_score", 0),
                "Momentum": sig.get("momentum_score", 0),
                "Vol Stretch": sig.get("volatility_score", 0),
                "Volume": sig.get("volume_score", 0),
                "Reasons": ", ".join(sig.get("reasons", [])[:2]),
            })

    if rows:
        df = pd.DataFrame(rows)

        # Color-code the Signal column
        def color_signal(val):
            if val > 0.2:
                return 'background-color: #00B87C20; color: #00B87C; font-weight: 600;'
            elif val < -0.2:
                return 'background-color: #E84D4D20; color: #E84D4D; font-weight: 600;'
            return 'background-color: #F5A62320; color: #F5A623; font-weight: 600;'

        styled = df.style.applymap(color_signal, subset=['Signal'])

        # Format columns
        styled = styled.format({
            'Signal': '{:.2f}',
            'Trend': '{:.2f}',
            'Momentum': '{:.2f}',
            'Vol Stretch': '{:.2f}',
            'Volume': '{:.2f}',
        })

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Signal": st.column_config.ProgressColumn("Signal", min_value=-1, max_value=1, format="%.2f"),
            }
        )
    else:
        empty_state("📊", "No Signals", "Unable to load signal data")