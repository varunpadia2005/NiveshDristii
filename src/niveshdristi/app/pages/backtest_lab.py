"""Backtest Lab page: Strategy testing with Groww-inspired design."""
import streamlit as st
import pandas as pd
from niveshdristi.app.components import (
    page_header, render_disclaimer, metric_card, quick_stats_row,
    empty_state, tag, signal_badge
)


def render(api_get):
    
    page_header("Backtest Lab", "Test and validate trading strategies with honest backtesting", "🧪")
    
    # Strategy selector
    col1, col2, col3 = st.columns(3)
    with col1:
        strategy = st.selectbox(
            "Strategy",
            ["Signal-Based", "Mean Reversion", "Trend Following", "ML-Based", "Buy & Hold"],
            help="Select the strategy to backtest"
        )
    with col2:
        universe = st.selectbox(
            "Universe",
            ["Nifty 10", "Nifty 50", "Custom"],
            help="Stock universe for backtest"
        )
    with col3:
        capital = st.number_input(
            "Initial Capital (₹)",
            value=1000000,
            step=100000,
            format="%d"
        )
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.Timestamp("2022-01-01"))
    with col2:
        end_date = st.date_input("End Date", value=pd.Timestamp("2024-01-01"))
    
    # Advanced settings
    with st.expander("⚙️ Advanced Settings"):
        col1, col2 = st.columns(2)
        with col1:
            slippage = st.number_input("Slippage (bps)", value=5, min_value=0, step=1)
            commission = st.number_input("Commission per order (₹)", value=20, min_value=0, step=10)
        with col2:
            max_pos = st.slider("Max Position %", 1, 20, 10)
            max_sector = st.slider("Max Sector %", 10, 50, 30)
    
    if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
        with st.spinner(f"Running {strategy} backtest..."):
            import requests
            tickers_param = ""  # Would need proper ticker list
            r = requests.get(
                f"http://localhost:8000/backtest",
                params={"tickers": "", "strategy": strategy.lower().replace(" ", "_")},
                timeout=60
            )
            
            if r.ok:
                data = r.json()
                metrics = data.get("metrics", {})
                
                # Results
                st.success("✅ Backtest completed")
                
                # Key metrics
                st.markdown("### Performance Metrics")
                stats = [
                    {"label": "CAGR", "value": f"{metrics.get('CAGR', 0)*100:.1f}%", "icon": "📈"},
                    {"label": "Volatility", "value": f"{metrics.get('Volatility', 0)*100:.1f}%", "icon": "📊"},
                    {"label": "Sharpe Ratio", "value": f"{metrics.get('Sharpe', 0):.2f}", "icon": "⚖️"},
                    {"label": "Max Drawdown", "value": f"{metrics.get('MaxDD', 0)*100:.1f}%", "change_type": "negative", "icon": "📉"},
                    {"label": "Total Trades", "value": str(metrics.get("Trades", 0)), "icon": "🔄"},
                ]
                quick_stats_row(stats)
                
                # Equity curve
                if data.get("equity_curve"):
                    import plotly.graph_objects as go
                    eq_df = pd.DataFrame(data["equity_curve"])
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=eq_df["date"], y=eq_df["equity"],
                        mode="lines", name="Equity",
                        line=dict(color="#00B87C", width=2),
                        fill="tozeroy", fillcolor="#00B87C15",
                    ))
                    fig.update_layout(
                        height=400, margin=dict(l=0,r=0,t=30,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=True, gridcolor="var(--chart-grid)"),
                        yaxis=dict(showgrid=True, gridcolor="var(--chart-grid)", title="Equity (₹)"),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Trade log
                if data.get("trades"):
                    st.markdown("### Trade Log")
                    trades_df = pd.DataFrame(data["trades"])
                    st.dataframe(trades_df, use_container_width=True, hide_index=True)
            else:
                st.error(f"Backtest failed: {r.status_code}")
    else:
        # Initial state
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px;">
            <div style="font-size: 64px; margin-bottom: 16px;">🧪</div>
            <h2 style="margin: 0 0 8px; color: var(--text-primary);">Backtest Lab</h2>
            <p style="margin: 0; color: var(--text-secondary); font-size: 16px;">
                Configure your strategy and click <strong>Run Backtest</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Strategy cards
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Available Strategies")
        
        strategies = [
            ("Signal-Based", "Uses composite technical signals for entries/exits", "📊"),
            ("Mean Reversion", "Buys oversold, sells overbought using RSI/Bollinger", "🔄"),
            ("Trend Following", "Follows EMA crossovers and MACD signals", "📈"),
            ("ML-Based", "Uses LightGBM model predictions for signals", "🤖"),
            ("Buy & Hold", "Benchmark: equal weight portfolio, no trading", "💰"),
        ]
        
        cols = st.columns(len(strategies))
        for i, (name, desc, icon) in enumerate(strategies):
            with cols[i]:
                st.markdown(f"""
                <div class="nv-card" style="padding: 20px; text-align: center; height: 100%;">
                    <div style="font-size: 32px; margin-bottom: 12px;">{icon}</div>
                    <div style="font-weight: 600; font-size: 16px; color: var(--text-primary); margin-bottom: 8px;">{name}</div>
                    <div style="font-size: 13px; color: var(--text-secondary);">{desc}</div>
                </div>
                """, unsafe_allow_html=True)


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()