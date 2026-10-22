"""Screener page: Advanced filtering with Groww-inspired design."""
import streamlit as st
import pandas as pd
import asyncio
from niveshdristi.config import CFG
from niveshdristi.app.components import (
    page_header, render_disclaimer, metric_card, stock_card, 
    quick_stats_row, empty_state, tag, watchlist_table
)
from niveshdristi.data.loader import load_prices
from niveshdristi.fundamentals.loader import load_fundamentals
from niveshdristi.indicators import compute_all_indicators
from niveshdristi.signals import generate_signal_report
from niveshdristi.fundamentals.loader import check_guardrails


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()
    
    # Page header
    page_header("Stock Screener", "Filter stocks by technical and fundamental criteria", "🔎")
    
    # Filter sidebar
    with st.sidebar:
        st.markdown("### Filters")
        
        # Technical filters
        st.markdown("#### Technical")
        min_composite = st.slider("Min Composite", -1.0, 1.0, -1.0, 0.1, help="Overall signal score")
        min_trend = st.slider("Min Trend", -1.0, 1.0, -1.0, 0.1)
        min_momentum = st.slider("Min Momentum", -1.0, 1.0, -1.0, 0.1)
        
        st.markdown("#### Fundamental")
        max_pe = st.number_input("Max P/E", value=50, min_value=0, step=5, help="Price to Earnings ratio")
        max_de = st.number_input("Max D/E", value=200, min_value=0, step=10, help="Debt to Equity ratio")
        min_roe = st.number_input("Min ROE (%)", value=0, min_value=0, step=5, help="Return on Equity")
        min_margin = st.number_input("Min Profit Margin (%)", value=0, min_value=0, step=1, help="Net profit margin")
        
        # Sector filter
        universe = CFG.data.universe
        sectors = list(set([
            api_get(f"/fundamentals/{t}").get("fundamentals", {}).get("sector", "Unknown") 
            for t in universe[:10]  # Sample for speed
        ]))
        selected_sectors = st.multiselect("Sectors", sectors, default=sectors)
        
        # Universe
        universe_name = st.selectbox("Universe", ["nifty10", "nifty50", "custom"], index=0)
        
        run_screen = st.button("Run Screen", type="primary", use_container_width=True)
    
    # Main content area
    if run_screen:
        with st.spinner(f"Screening {len(universe)} stocks..."):
            results = []
            universe_tickers = CFG.data.universe if universe_name != "custom" else []
            
            for t in universe_tickers:
                try:
                    pd = asyncio.run(load_prices(t))
                    df = compute_all_indicators(pd.df)
                    sig = generate_signal_report(t, df)
                    
                    if sig.composite < min_composite:
                        continue
                    if sig.trend_score < min_trend:
                        continue
                    if sig.momentum_score < min_momentum:
                        continue
                    
                    fund = asyncio.run(load_fundamentals(t))
                    
                    if fund.pe_ratio and fund.pe_ratio > max_pe:
                        continue
                    if fund.debt_to_equity and fund.debt_to_equity > max_de:
                        continue
                    if fund.roe and fund.roe * 100 < min_roe:
                        continue
                    if fund.profit_margin and fund.profit_margin * 100 < min_margin:
                        continue
                    if fund.sector not in selected_sectors:
                        continue
                    
                    guard = check_guardrails(fund)
                    
                    results.append({
                        "ticker": t,
                        "composite": sig.composite,
                        "trend": sig.trend_score,
                        "momentum": sig.momentum_score,
                        "vol_stretch": sig.volatility_score,
                        "volume": sig.volume_score,
                        "price": round(pd.df["adj_close"].iloc[-1], 1),
                        "pe": round(fund.pe_ratio, 1) if fund.pe_ratio else None,
                        "de": round(fund.debt_to_equity, 2) if fund.debt_to_equity else None,
                        "roe": fund.roe * 100 if fund.roe else None,
                        "margin": fund.profit_margin * 100 if fund.profit_margin else None,
                        "sector": fund.sector,
                        "signal": "Bullish" if sig.composite > 0.2 else "Bearish" if sig.composite < -0.2 else "Neutral",
                        "guardrail_cap": guard["max_score_cap"],
                    })
                except Exception as e:
                    continue
            
            if results:
                st.success(f"Found {len(results)} matching stocks")
                
                # Summary stats
                bullish = sum(1 for r in results if r["composite"] > 0.2)
                bearish = sum(1 for r in results if r["composite"] < -0.2)
                
                stats = [
                    {"label": "Total Matches", "value": str(len(results)), "icon": "OK"},
                    {"label": "Bullish", "value": str(bullish), "change_type": "positive", "icon": "Bullish"},
                    {"label": "Bearish", "value": str(bearish), "change_type": "negative", "icon": "Bearish"},
                    {"label": "Avg Score", "value": f"{sum(r['composite'] for r in results)/len(results):.2f}", "icon": "Chart"},
                ]
                quick_stats_row(stats)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Results table
                st.markdown("### Results")
                
                df = pd.DataFrame(results)
                
                # Configure display
                df_display = df.copy()
                df_display["PE"] = df_display["pe"].apply(lambda x: f"{x:.1f}" if x else "N/A")
                df_display["D/E"] = df_display["de"].apply(lambda x: f"{x:.2f}" if x else "N/A")
                df_display["ROE"] = df_display["roe"].apply(lambda x: f"{x:.1f}%" if x else "N/A")
                df_display["Margin"] = df_display["margin"].apply(lambda x: f"{x:.1f}%" if x else "N/A")
                df_display["Score"] = df_display["composite"].apply(lambda x: f"{x:.2f}")
                df_display["Trend"] = df_display["trend"].apply(lambda x: f"{x:.2f}")
                df_display["Momentum"] = df_display["momentum"].apply(lambda x: f"{x:.2f}")
                df_display["Cap"] = df_display["guardrail_cap"].apply(lambda x: f"{x}")
                
                # Select columns to show
                show_cols = ["ticker", "sector", "price", "Signal", "Score", "Trend", "Momentum", "PE", "D/E", "ROE", "Margin", "Cap"]
                
                st.dataframe(
                    df_display[show_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "ticker": st.column_config.TextColumn("Symbol", width="small"),
                        "sector": st.column_config.TextColumn("Sector", width="small"),
                        "price": st.column_config.NumberColumn("Price", format="INR %.1f", width="small"),
                        "Signal": st.column_config.TextColumn("Signal", width="small"),
                        "Score": st.column_config.TextColumn("Score", width="small"),
                        "Trend": st.column_config.TextColumn("Trend", width="small"),
                        "Momentum": st.column_config.TextColumn("Momentum", width="small"),
                        "PE": st.column_config.TextColumn("P/E", width="small"),
                        "D/E": st.column_config.TextColumn("D/E", width="small"),
                        "ROE": st.column_config.TextColumn("ROE %", width="small"),
                        "Margin": st.column_config.TextColumn("Margin %", width="small"),
                        "Cap": st.column_config.TextColumn("Cap", width="small"),
                    }
                )
                
                # Quick cards view
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### Quick View")
                
                # Show top 6 as cards
                for r in results[:6]:
                    with st.container():
                        stock_card(r["ticker"], 
                                 {"composite": r["composite"], "trend_score": r["trend"], "momentum_score": r["momentum"], 
                                  "volatility_score": r["vol_stretch"], "volume_score": r["volume"]},
                                 {"last_price": r["price"]},
                                 {"pe_ratio": r["pe"], "debt_to_equity": r["de"], "roe": r["roe"]/100 if r["roe"] else None,
                                  "profit_margin": r["margin"]/100 if r["margin"] else None})
                
            else:
                empty_state(
                    "Search", 
                    "No Matches Found", 
                    "Try relaxing your filter criteria or expanding the universe",
                    "Clear Filters", "clear_filters"
                )
    else:
        # Initial state
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px;">
            <div style="font-size: 64px; margin-bottom: 16px;">Search</div>
            <h2 style="margin: 0 0 8px; color: var(--text-primary);">Stock Screener</h2>
            <p style="margin: 0; color: var(--text-secondary); font-size: 16px;">
                Set your filters in the sidebar and click <strong>Run Screen</strong> to find matching stocks
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick preset buttons
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Quick Presets")
        
        cols = st.columns(4)
        presets = [
            ("Quality Momentum", {"min_composite": 0.3, "min_roe": 15, "max_de": 50}),
            ("Trend Followers", {"min_trend": 0.5, "min_momentum": 0.3}),
            ("Value Picks", {"max_pe": 20, "min_margin": 10}),
            ("Safe Bets", {"max_de": 30, "min_roe": 12, "min_margin": 8}),
        ]
        
        for i, (name, params) in enumerate(presets):
            with cols[i]:
                if st.button(name, key=f"preset_{i}", use_container_width=True):
                    # Set session state for filters (would need more complex state management)
                    st.info(f"Preset '{name}' selected - adjust filters manually for now")