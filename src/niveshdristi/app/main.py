"""Streamlit UI entry point."""
import streamlit as st
from niveshdristi.config import CFG
from niveshdristi.app.theme import theme_toggle
from niveshdristi.app.pages import (
    dashboard, deep_dive, screener,
    sector_rotation, backtest_lab, portfolio_builder,
    ai_analyst, methodology
)

st.set_page_config(
    page_title="NiveshDristi",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Theme toggle (must run first to apply CSS)
theme_toggle()

# Sidebar navigation
st.sidebar.title("📈 NiveshDristi")
st.sidebar.caption("Investment Vision — Research Assistant")

page_map = {
    "dashboard": ("📊 Dashboard", dashboard),
    "deep_dive": ("🔍 Deep-Dive", deep_dive),
    "screener": ("🔎 Screener", screener),
    "sector_rotation": ("🌍 Sector Rotation", sector_rotation),
    "backtest_lab": ("🧪 Backtest Lab", backtest_lab),
    "portfolio_builder": ("💼 Portfolio", portfolio_builder),
    "ai_analyst": ("🤖 AI Analyst", ai_analyst),
    "methodology": ("📚 Methodology", methodology),
}

page = st.sidebar.radio(
    "Navigate",
    CFG.app.pages,
    format_func=lambda x: page_map[x][0]
)

st.sidebar.divider()
st.sidebar.warning(
    "**Disclaimer:** Educational research tool. "
    "Not investment advice. No SEBI registration.",
    icon="⚠️"
)

# Simple API helper
def api_get(path: str):
    import requests
    try:
        base = "http://localhost:8000"
        resp = requests.get(f"{base}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None

# Route to page
page_module = page_map[page][1]
page_module.render(api_get)