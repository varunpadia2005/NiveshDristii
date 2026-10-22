"""Sector Rotation page: RRG visualization with Groww-inspired design."""
import streamlit as st
import pandas as pd
import numpy as np
from niveshdristi.app.components import (
    page_header, render_disclaimer, regime_indicator, 
    sector_quadrant_chart, quick_stats_row, empty_state, tag
)


def render(api_get):
    
    page_header("Sector Rotation", "Track sector momentum and rotation with Relative Rotation Graph", "🌍")
    
    # Load regime data
    with st.spinner("Loading sector rotation data..."):
        regime = api_get("/regime")
    
    if not regime:
        empty_state("🌍", "No Data", "Unable to load regime data")
        return
    
    # Market regime indicator
    regime_indicator(regime.get("market_state", "unknown"), regime.get("vix_level", 15))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Stats row
    sectors = regime.get("sectors", {})
    if sectors:
        leading = sum(1 for q in sectors.values() if q == "Leading")
        weakening = sum(1 for q in sectors.values() if q == "Weakening")
        lagging = sum(1 for q in sectors.values() if q == "Lagging")
        improving = sum(1 for q in sectors.values() if q == "Improving")
        
        stats = [
            {"label": "Leading", "value": str(leading), "change_type": "positive", "icon": "🟢"},
            {"label": "Weakening", "value": str(weakening), "change_type": "warning", "icon": "🟡"},
            {"label": "Lagging", "value": str(lagging), "change_type": "negative", "icon": "🔴"},
            {"label": "Improving", "value": str(improving), "change_type": "info", "icon": "🔵"},
        ]
        quick_stats_row(stats)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # RRG Chart
    st.markdown("### Relative Rotation Graph (RRG)")
    st.markdown("""
    <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.5;">
        RRG plots sectors on two axes: <strong>RS-Ratio</strong> (relative strength vs Nifty) vs 
        <strong>RS-Momentum</strong> (momentum of that relative strength). Sectors rotate clockwise:
        <span style="color: #00B87C;">🟢 Leading</span> → 
        <span style="color: #F5A623;">🟡 Weakening</span> → 
        <span style="color: #E84D4D;">🔴 Lagging</span> → 
        <span style="color: #007AFF;">🔵 Improving</span> → repeat.
    </div>
    """, unsafe_allow_html=True)
    
    from niveshdristi.app.components import sector_quadrant_chart
    st.plotly_chart(
        sector_quadrant_chart(sectors),
        use_container_width=True
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Sector table
    st.markdown("### Sector Details")
    
    quad_data = []
    quad_colors = {
        "Leading": ("🟢", "#00B87C", "Strong & Strengthening"),
        "Weakening": ("🟡", "#F5A623", "Strong but Fading"),
        "Lagging": ("🔴", "#E84D4D", "Weak & Weakening"),
        "Improving": ("🔵", "#007AFF", "Weak but Strengthening"),
    }
    
    for sector, quad in sectors.items():
        icon, color, desc = quad_colors.get(quad, ("⚪", "#888", "Unknown"))
        quad_data.append({
            "Sector": sector,
            "Quadrant": f'<span style="background: {color}20; color: {color}; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;">{icon} {quad}</span>',
            "Description": f'<span style="color: var(--text-secondary); font-size: 13px;">{desc}</span>',
        })
    
    if quad_data:
        df = pd.DataFrame(quad_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # RRG Trail (placeholder)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### RRG Trail (Coming Soon)")
    st.info("Historical sector rotation trails showing the path of each sector through quadrants over time")


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()