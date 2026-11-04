"""Portfolio Builder page: Portfolio optimization with Groww-inspired design."""
import streamlit as st
import pandas as pd
from niveshdristi.app.components import (
    page_header, render_disclaimer, metric_card, quick_stats_row, 
    empty_state, tag
)
from niveshdristi.app.theme import theme_toggle


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()
    
    page_header("Portfolio Builder", "Construct and optimize portfolios with risk management", "Portfolio")
    
    # Portfolio builder steps
    step = st.session_state.get("portfolio_step", 1)
    
    # Progress indicator
    steps = ["Select Stocks", "Optimize", "Review"]
    cols = st.columns(3)
    for i, (step_name, col) in enumerate(zip(steps, cols)):
        with col:
            is_active = i + 1 == step
            st.markdown(f"""
            <div style="text-align: center; padding: 16px; 
                        background: {'var(--brand-light)' if is_active else 'var(--bg-secondary)'}; 
                        border: 2px solid {'var(--brand-primary)' if is_active else 'var(--border-light)'};
                        border-radius: 12px;">
                <div style="font-size: 12px; color: {'var(--brand-primary)' if is_active else 'var(--text-muted)'}; text-transform: uppercase;">Step {i+1}</div>
                <div style="font-weight: 600; color: {'var(--text-primary)' if is_active else 'var(--text-secondary)'};">{step_name}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if step == 1:
        st.markdown("### Step 1: Select Stocks")
        
        universe = CFG.data.universe
        selected = st.multiselect(
            "Select stocks for portfolio",
            universe,
            default=universe[:5],
            format_func=lambda x: x,
            placeholder="Choose stocks..."
        )
        
        if selected:
            # Quick preview
            st.markdown("### Selected Stocks Preview")
            cols = st.columns(min(len(selected), 4))
            for i, t in enumerate(selected):
                with cols[i % 4]:
                    st.markdown(f"""
                    <div class="nv-card" style="text-align: center; padding: 16px;">
                        <div style="font-weight: 600; font-size: 16px;">{t}</div>
                        <div style="font-size: 12px; color: var(--text-secondary);">Selected</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            if st.button("Next: Optimize", type="primary", use_container_width=True):
                st.session_state.portfolio_step = 2
                st.session_state.portfolio_stocks = selected
                st.rerun()
    
    elif step == 2:
        st.markdown("### Step 2: Configure Optimization")
        
        selected = st.session_state.get("portfolio_stocks", [])
        
        col1, col2 = st.columns(2)
        with col1:
            optimizer = st.selectbox(
                "Optimization Method",
                ["Equal Weight", "Minimum Variance", "Maximum Sharpe", "HRP (Hierarchical Risk Parity)", "Black-Litterman"],
                help="Portfolio optimization algorithm"
            )
            
            rebalance = st.selectbox(
                "Rebalancing Frequency",
                ["Monthly", "Quarterly", "Semi-Annually", "Annually"],
                index=0
            )
        
        with col2:
            max_pos = st.slider("Max Position %", 1, 30, 10)
            max_sector = st.slider("Max Sector %", 10, 50, 30)
            max_positions = st.slider("Max Positions", 5, 30, 15)
            
            risk_target = st.number_input("Risk Target (Annual Vol %)", value=15.0, step=1.0)
        
        # Risk models
        st.markdown("### Risk Model")
        risk_model = st.radio(
            "Covariance Estimation",
            ["Sample Covariance", "Ledoit-Wolf Shrinkage", "Exponential Weighted"],
            horizontal=True,
            help="How to estimate the covariance matrix"
        )
        
        if st.button("Optimize Portfolio", type="primary", use_container_width=True):
            with st.spinner("Optimizing portfolio..."):
                import time
                time.sleep(2)
                
                # Simulate optimization
                weights = {t: 1/len(selected) for t in selected}  # Equal weight for demo
                
                st.session_state.portfolio_weights = weights
                st.session_state.portfolio_step = 3
                st.rerun()
    
    elif step == 3:
        st.markdown("### Step 3: Portfolio Review")
        
        weights = st.session_state.get("portfolio_weights", {})
        
        if weights:
            # Summary metrics
            stats = [
                {"label": "Stocks", "value": str(len(weights)), "icon": "Chart"},
                {"label": "Concentration (HHI)", "value": f"{sum(w**2 for w in weights.values()):.4f}", "icon": "Chart"},
                {"label": "Max Weight", "value": f"{max(weights.values())*100:.1f}%", "icon": "Balance"},
                {"label": "Est. Annual Vol", "value": "~15.2%", "icon": "Chart Down"},
            ]
            quick_stats_row(stats)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Weights table
            st.markdown("### Portfolio Weights")
            
            df = pd.DataFrame([
                {"Stock": t, "Weight": f"{w*100:.1f}%", "Weight %": w*100}
                for t, w in sorted(weights.items(), key=lambda x: -x[1])
            ])
            
            # Bar chart
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(
                y=df["Stock"], x=df["Weight %"],
                orientation='h', marker_color="#00B87C",
                text=df["Weight"], textposition='outside',
            ))
            fig.update_layout(
                height=300, margin=dict(l=0,r=0,t=10,b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="var(--chart-grid)"),
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Full table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Stock": st.column_config.TextColumn("Stock", width="small"),
                    "Weight": st.column_config.TextColumn("Weight", width="small"),
                }
            )
            
            # Actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Export CSV", use_container_width=True):
                    st.toast("Portfolio exported!")
            with col2:
                if st.button("Re-optimize", use_container_width=True):
                    st.session_state.portfolio_step = 2
                    st.rerun()
            with col3:
                if st.button("Save Portfolio", type="primary", use_container_width=True):
                    st.toast("Portfolio saved!")