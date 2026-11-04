"""Theme system: Light default with dark mode toggle - Groww-inspired."""
import streamlit as st
from niveshdristi.config import CFG


# Groww-inspired color palette - Light, clean, professional
LIGHT_THEME = {
    # Backgrounds - clean whites and off-whites
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#FAFAFB", 
    "bg_tertiary": "#F5F6FA",
    "bg_card": "#FFFFFF",
    "bg_hover": "#F0F2F5",
    "bg_input": "#FAFAFB",
    
    # Text
    "text_primary": "#1A1D21",
    "text_secondary": "#5E6C84",
    "text_muted": "#9AA7B8",
    "text_on_primary": "#FFFFFF",
    
    # Brand - Groww green
    "brand_primary": "#00B87C",
    "brand_secondary": "#00A06D",
    "brand_light": "#E8F8F0",
    "brand_gradient": "linear-gradient(135deg, #00B87C 0%, #00D48A 100%)",
    
    # Semantic
    "success": "#00B87C",
    "success_light": "#E8F8F0",
    "danger": "#E84D4D",
    "danger_light": "#FDEDED",
    "warning": "#F5A623",
    "warning_light": "#FFF4E6",
    "info": "#007AFF",
    "info_light": "#E8F0FE",
    
    # Borders
    "border_light": "#E4E7EC",
    "border_medium": "#D1D5DB",
    "border_focus": "#00B87C",
    
    # Charts
    "chart_grid": "#F0F2F5",
    "chart_text": "#5E6C84",
    
    # Shadows
    "shadow_sm": "0 1px 2px rgba(0,0,0,0.04)",
    "shadow_md": "0 4px 12px rgba(0,0,0,0.06)",
    "shadow_lg": "0 12px 24px rgba(0,0,0,0.08)",
    "shadow_glow": "0 0 0 3px #00B87C33",
}

DARK_THEME = {
    "bg_primary": "#0D1117",
    "bg_secondary": "#161B22",
    "bg_tertiary": "#1C2128",
    "bg_card": "#161B22",
    "bg_hover": "#1F2937",
    "bg_input": "#1C2128",
    
    "text_primary": "#F0F6FC",
    "text_secondary": "#8B949E",
    "text_muted": "#6E7681",
    "text_on_primary": "#FFFFFF",
    
    "brand_primary": "#00D48A",
    "brand_secondary": "#00C07D",
    "brand_light": "#0D2818",
    "brand_gradient": "linear-gradient(135deg, #00D48A 0%, #00B87C 100%)",
    
    "success": "#00D48A",
    "success_light": "#0D2818",
    "danger": "#F85149",
    "danger_light": "#2D1010",
    "warning": "#F5A623",
    "warning_light": "#2D1F00",
    "info": "#58A6FF",
    "info_light": "#0D1F2D",
    
    "border_light": "#30363D",
    "border_medium": "#484F58",
    "border_focus": "#00D48A",
    
    "chart_grid": "#21262D",
    "chart_text": "#8B949E",
    
    "shadow_sm": "0 1px 2px rgba(0,0,0,0.2)",
    "shadow_md": "0 4px 12px rgba(0,0,0,0.3)",
    "shadow_lg": "0 12px 24px rgba(0,0,0,0.4)",
    "shadow_glow": "0 0 0 3px #00D48A33",
}


def apply_theme(theme: dict):
    """Apply theme via CSS custom properties with Groww-inspired styling."""
    css = f"""
    <style>
    :root {{
        --bg-primary: {theme['bg_primary']};
        --bg-secondary: {theme['bg_secondary']};
        --bg-tertiary: {theme['bg_tertiary']};
        --bg-card: {theme['bg_card']};
        --bg-hover: {theme['bg_hover']};
        --bg-input: {theme['bg_input']};
        --text-primary: {theme['text_primary']};
        --text-secondary: {theme['text_secondary']};
        --text-muted: {theme['text_muted']};
        --text-on-primary: {theme['text_on_primary']};
        --brand-primary: {theme['brand_primary']};
        --brand-secondary: {theme['brand_secondary']};
        --brand-light: {theme['brand_light']};
        --brand-gradient: {theme['brand_gradient']};
        --success: {theme['success']};
        --success-light: {theme['success_light']};
        --danger: {theme['danger']};
        --danger-light: {theme['danger_light']};
        --warning: {theme['warning']};
        --warning-light: {theme['warning_light']};
        --info: {theme['info']};
        --info-light: {theme['info_light']};
        --border-light: {theme['border_light']};
        --border-medium: {theme['border_medium']};
        --border-focus: {theme['border_focus']};
        --chart-grid: {theme['chart_grid']};
        --chart-text: {theme['chart_text']};
        --shadow-sm: {theme['shadow_sm']};
        --shadow-md: {theme['shadow_md']};
        --shadow-lg: {theme['shadow_lg']};
        --shadow-glow: {theme['shadow_glow']};
    }}
    
    /* ==================== GLOBAL RESETS ==================== */
    .stApp {{
        background: var(--bg-primary);
        color: var(--text-primary);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    /* Remove default Streamlit padding */
    .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }}
    
    /* ==================== SIDEBAR ==================== */
    [data-testid="stSidebar"] {{
        background: var(--bg-secondary);
        border-right: 1px solid var(--border-light);
        padding-top: 1rem;
    }}
    
    [data-testid="stSidebar"] .stMarkdown {{
        color: var(--text-primary);
    }}
    
    [data-testid="stSidebar"] .stRadio > label {{
        font-weight: 500;
        color: var(--text-primary);
    }}
    
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {{
        background: var(--brand-primary) !important;
    }}
    
    /* ==================== CARDS ==================== */
    .nv-card {{
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: var(--shadow-sm);
    }}
    .nv-card:hover {{
        border-color: var(--border-medium);
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }}
    .nv-card-compact {{
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 10px;
        padding: 14px;
    }}
    .nv-card-animated {{
        animation: fadeInScale 0.5s ease-out forwards;
        opacity: 0;
    }}
    .nv-card-animated:nth-child(1) {{ animation-delay: 0.05s; }}
    .nv-card-animated:nth-child(2) {{ animation-delay: 0.1s; }}
    .nv-card-animated:nth-child(3) {{ animation-delay: 0.15s; }}
    .nv-card-animated:nth-child(4) {{ animation-delay: 0.2s; }}
    .nv-card-animated:nth-child(5) {{ animation-delay: 0.25s; }}
    .nv-card-animated:nth-child(6) {{ animation-delay: 0.3s; }}
    
    .nv-stagger-in > * {{
        animation: slideUp 0.5s ease-out forwards;
        opacity: 0;
    }}
    .nv-stagger-in > *:nth-child(1) {{ animation-delay: 0.05s; }}
    .nv-stagger-in > *:nth-child(2) {{ animation-delay: 0.1s; }}
    .nv-stagger-in > *:nth-child(3) {{ animation-delay: 0.15s; }}
    .nv-stagger-in > *:nth-child(4) {{ animation-delay: 0.2s; }}
    .nv-stagger-in > *:nth-child(5) {{ animation-delay: 0.25s; }}
    .nv-stagger-in > *:nth-child(6) {{ animation-delay: 0.3s; }}
    
    @keyframes fadeInScale {{
        from {{ opacity: 0; transform: scale(0.95); }}
        to {{ opacity: 1; transform: scale(1); }}
    }}
    @keyframes slideUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* ==================== METRICS ==================== */
    .nv-metric {{
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 12px;
        padding: 16px;
        transition: all 0.2s ease;
    }}
    .nv-metric:hover {{
        border-color: var(--border-medium);
        box-shadow: var(--shadow-md);
    }}
    .nv-metric-label {{
        font-size: 11px;
        font-weight: 500;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}
    .nv-metric-value {{
        font-size: 24px;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.2;
    }}
    .nv-metric-change {{
        font-size: 12px;
        font-weight: 600;
        margin-top: 4px;
    }}
    .nv-change-positive {{ color: var(--success); }}
    .nv-change-negative {{ color: var(--danger); }}
    .nv-change-neutral {{ color: var(--warning); }}
    
    /* Streamlit metric override */
    [data-testid="stMetric"] {{
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 12px;
        padding: 16px;
        box-shadow: var(--shadow-sm);
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--text-secondary) !important;
        font-size: 11px !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    [data-testid="stMetricValue"] {{
        color: var(--text-primary) !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 12px !important;
        font-weight: 600 !important;
    }}
    
    /* ==================== BUTTONS ==================== */
    .stButton > button {{
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 12px 24px !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: none !important;
    }}
    .stButton > button[kind="primary"] {{
        background: var(--brand-gradient) !important;
        color: white !important;
        box-shadow: 0 4px 14px var(--brand-primary)40 !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px var(--brand-primary)50 !important;
    }}
    .stButton > button[kind="primary"]:active {{
        transform: translateY(0) !important;
    }}
    .stButton > button[kind="secondary"] {{
        background: var(--bg-card) !important;
        border: 1px solid var(--border-light) !important;
        color: var(--text-primary) !important;
    }}
    .stButton > button[kind="secondary"]:hover {{
        background: var(--bg-hover) !important;
        border-color: var(--border-medium) !important;
    }}
    .stButton > button:focus {{
        outline: none !important;
        box-shadow: var(--shadow-glow) !important;
    }}
    
    /* ==================== TABS ==================== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: transparent;
        border-bottom: 1px solid var(--border-light);
        padding-bottom: 0;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        border: none;
        border-radius: 10px 10px 0 0;
        padding: 14px 24px;
        font-weight: 500;
        color: var(--text-secondary);
        border-bottom: 3px solid transparent;
        transition: all 0.15s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: var(--text-primary);
        background: var(--bg-hover);
    }}
    .stTabs [aria-selected="true"] {{
        color: var(--brand-primary) !important;
        border-bottom-color: var(--brand-primary) !important;
        background: var(--brand-light) !important;
    }}
    
    /* ==================== INPUTS ==================== */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
    }}
    .stSelectbox > div > div:hover,
    .stMultiSelect > div > div:hover {{
        border-color: var(--border-medium) !important;
    }}
    .stSelectbox > div > div:focus-within,
    .stMultiSelect > div > div:focus-within {{
        border-color: var(--border-focus) !important;
        box-shadow: var(--shadow-glow) !important;
    }}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        padding: 12px 16px !important;
        font-size: 15px !important;
        transition: all 0.2s ease !important;
    }}
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {{
        border-color: var(--border-focus) !important;
        box-shadow: var(--shadow-glow) !important;
    }}
    .stDateInput > div > div > input {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 10px !important;
    }}
    
    /* ==================== DATAFRAME ==================== */
    .stDataFrame {{
        border: 1px solid var(--border-light) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    .stDataFrame [data-testid="stTable"] {{
        background: var(--bg-card) !important;
    }}
    .stDataFrame thead th {{
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid var(--border-light) !important;
        padding: 12px 16px !important;
    }}
    .stDataFrame tbody td {{
        padding: 12px 16px !important;
        border-bottom: 1px solid var(--border-light) !important;
        color: var(--text-primary) !important;
    }}
    .stDataFrame tbody tr:hover td {{
        background: var(--bg-hover) !important;
    }}
    
    /* ==================== EXPANDER ==================== */
    .streamlit-expanderHeader {{
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
        padding: 12px 16px !important;
    }}
    .streamlit-expanderContent {{
        border: 1px solid var(--border-light) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        background: var(--bg-card) !important;
        padding: 16px !important;
    }}
    
    /* ==================== PROGRESS BAR ==================== */
    .stProgress > div > div {{
        background: var(--brand-gradient) !important;
        border-radius: 4px !important;
    }}
    .stProgress > div {{
        background: var(--bg-secondary) !important;
        border-radius: 4px !important;
        height: 8px !important;
    }}
    
    /* ==================== TOOLTIP ==================== */
    .stTooltipContent {{
        background: var(--bg-card) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        box-shadow: var(--shadow-lg) !important;
    }}
    
    /* ==================== SCROLLBAR ==================== */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: var(--bg-secondary);
    }}
    ::-webkit-scrollbar-thumb {{
        background: var(--border-medium);
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: var(--text-muted);
    }}
    
    /* ==================== ANIMATIONS ==================== */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .nv-fade-in {{
        animation: fadeIn 0.3s ease-out;
    }}
    
    @keyframes shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}
    .nv-shimmer {{
        background: linear-gradient(90deg, 
            var(--text-secondary) 0%, 
            var(--brand-primary) 50%, 
            var(--text-secondary) 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: shimmer 3s linear infinite;
    }}
    
    @keyframes pulseGlow {{
        0%, 100% {{ opacity: 0.2; transform: scale(1); }}
        50% {{ opacity: 0.5; transform: scale(1.1); }}
    }}
    
    @keyframes floatOrb {{
        0%, 100% {{ transform: translate(0, 0) scale(1); opacity: 0.3; }}
        25% {{ transform: translate(30px, -20px) scale(1.1); opacity: 0.4; }}
        50% {{ transform: translate(-20px, 30px) scale(0.9); opacity: 0.5; }}
        75% {{ transform: translate(-30px, -10px) scale(1.05); opacity: 0.4; }}
    }}
    
    @keyframes slideUp {{
        from {{ opacity: 0; transform: translateY(30px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    @keyframes fadeInScale {{
        from {{ opacity: 0; transform: scale(0.95); }}
        to {{ opacity: 1; transform: scale(1); }}
    }}
    
    .nv-card-animated {{
        animation: fadeInScale 0.5s ease-out forwards;
        opacity: 0;
    }}
    .nv-card-animated:nth-child(1) {{ animation-delay: 0.05s; }}
    .nv-card-animated:nth-child(2) {{ animation-delay: 0.1s; }}
    .nv-card-animated:nth-child(3) {{ animation-delay: 0.15s; }}
    .nv-card-animated:nth-child(4) {{ animation-delay: 0.2s; }}
    .nv-card-animated:nth-child(5) {{ animation-delay: 0.25s; }}
    .nv-card-animated:nth-child(6) {{ animation-delay: 0.3s; }}
    
    .nv-stagger-in > * {{
        animation: slideUp 0.5s ease-out forwards;
        opacity: 0;
    }}
    .nv-stagger-in > *:nth-child(1) {{ animation-delay: 0.05s; }}
    .nv-stagger-in > *:nth-child(2) {{ animation-delay: 0.1s; }}
    .nv-stagger-in > *:nth-child(3) {{ animation-delay: 0.15s; }}
    .nv-stagger-in > *:nth-child(4) {{ animation-delay: 0.2s; }}
    .nv-stagger-in > *:nth-child(5) {{ animation-delay: 0.25s; }}
    .nv-stagger-in > *:nth-child(6) {{ animation-delay: 0.3s; }}
    
    .nv-pulse-ring {{
        position: absolute;
        border: 2px solid var(--brand-primary);
        border-radius: 50%;
        animation: pulseGlow 2s ease-out infinite;
    }}
    
    /* ==================== LOGIN PAGE SPECIFIC ==================== */
    .nv-login-container {{
        display: flex;
        min-height: 100vh;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }}
    
    .nv-login-card {{
        width: 100%;
        max-width: 420px;
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: 16px;
        padding: 40px 32px;
        box-shadow: var(--shadow-lg);
    }}
    
    .nv-login-header {{
        text-align: center;
        margin-bottom: 32px;
    }}
    
    .nv-login-logo {{
        width: 64px;
        height: 64px;
        border-radius: 16px;
        background: var(--brand-gradient);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
        box-shadow: 0 8px 24px var(--brand-primary)40;
    }}
    
    .nv-login-title {{
        font-size: 24px;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 8px;
    }}
    
    .nv-login-subtitle {{
        font-size: 14px;
        color: var(--text-secondary);
        margin-bottom: 0;
    }}
    
    .nv-input-group {{
        margin-bottom: 20px;
    }}
    
    .nv-input-label {{
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: var(--text-secondary);
        margin-bottom: 8px;
    }}
    
    .nv-input-wrapper {{
        position: relative;
    }}
    
    .nv-input {{
        width: 100%;
        padding: 14px 16px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-light);
        border-radius: 10px;
        color: var(--text-primary);
        font-size: 15px;
        transition: all 0.2s ease;
    }}
    
    .nv-input:focus {{
        outline: none;
        border-color: var(--brand-primary);
        box-shadow: 0 0 0 3px var(--brand-light);
    }}
    
    .nv-input-icon {{
        position: absolute;
        right: 14px;
        top: 50%;
        transform: translateY(-50%);
        color: var(--text-muted);
        font-size: 18px;
    }}
    
    .nv-btn-primary {{
        width: 100%;
        padding: 14px 24px;
        background: var(--brand-gradient);
        border: none;
        border-radius: 10px;
        color: white;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-top: 8px;
    }}
    
    .nv-btn-primary:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px var(--brand-primary)40;
    }}
    
    .nv-btn-primary:active {{
        transform: translateY(0);
    }}
    
    .nv-login-footer {{
        text-align: center;
        margin-top: 24px;
        font-size: 13px;
        color: var(--text-secondary);
    }}
    
    .nv-login-footer a {{
        color: var(--brand-primary);
        text-decoration: none;
        font-weight: 500;
    }}
    
    .nv-divider {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 24px 0;
        color: var(--text-muted);
        font-size: 13px;
    }}
    
    .nv-divider::before,
    .nv-divider::after {{
        content: "";
        flex: 1;
        height: 1px;
        background: var(--border-light);
    }}
    
    .nv-social-btn {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        padding: 12px 16px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-light);
        border-radius: 10px;
        color: var(--text-primary);
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    
    .nv-social-btn:hover {{
        background: var(--bg-hover);
        border-color: var(--border-medium);
    }}
    
    @media (prefers-reduced-motion: reduce) {{
        .nv-orb, .nv-grid-pattern, .nv-shimmer-text,
        .nv-card-animated, .nv-stagger-in > *,
        .nv-pulse-ring, .nv-shimmer {{
            animation: none !important;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def theme_toggle():
    """Render theme toggle button in top right."""
    if "theme" not in st.session_state:
        st.session_state.theme = CFG.app.theme_default
    
    theme = DARK_THEME if st.session_state.theme == "dark" else LIGHT_THEME
    apply_theme(theme)
    
    # Top-right toggle in sidebar
    with st.sidebar:
        st.markdown("---")
        cols = st.columns([3, 1])
        with cols[1]:
            icon = "🌙" if st.session_state.theme == "light" else "☀️"
            label = "Dark" if st.session_state.theme == "light" else "Light"
            # Use a unique key based on session to avoid conflicts
            toggle_key = f"theme_toggle_btn_{st.session_state.get('_theme_toggle_nonce', 0)}"
            if st.button(f"{icon}", key=toggle_key, help=f"Switch to {label} mode", use_container_width=True):
                st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
                # Increment nonce to force key change on next render (prevents duplicate key issues)
                st.session_state._theme_toggle_nonce = st.session_state.get('_theme_toggle_nonce', 0) + 1
                st.rerun()


def render_animated_background() -> None:
    """Render animated background orbs and subtle grid."""
    st.markdown("""
    <div class="nv-animated-bg">
        <div class="nv-orb nv-orb-1"></div>
        <div class="nv-orb nv-orb-2"></div>
        <div class="nv-orb nv-orb-3"></div>
        <div class="nv-grid-pattern"></div>
    </div>
    <style>
    .nv-animated-bg {{
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: -1;
        overflow: hidden;
    }}
    .nv-orb {{
        position: absolute;
        border-radius: 50%;
        filter: blur(80px);
        animation: floatOrb 20s ease-in-out infinite;
    }}
    .nv-orb-1 {{
        width: 400px; height: 400px;
        background: radial-gradient(circle, var(--brand-primary) 0%, transparent 70%);
        top: -100px; right: -100px;
        animation-delay: 0s;
    }}
    .nv-orb-2 {{
        width: 300px; height: 300px;
        background: radial-gradient(circle, var(--info) 0%, transparent 70%);
        bottom: -50px; left: -50px;
        animation-delay: -5s;
    }}
    .nv-orb-3 {{
        width: 250px; height: 250px;
        background: radial-gradient(circle, var(--warning) 0%, transparent 70%);
        top: 40%; left: 5%;
        animation-delay: -10s;
    }}
    .nv-grid-pattern {{
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: -1;
        opacity: 0.03;
        background-image: 
            linear-gradient(var(--border-light) 1px, transparent 1px),
            linear-gradient(90deg, var(--border-light) 1px, transparent 1px);
        background-size: 60px 60px;
        animation: slideUp 30s linear infinite;
    }}
    @media (prefers-reduced-motion: reduce) {{
        .nv-orb, .nv-grid-pattern {{
            animation: none !important;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = None, icon: str = ""):
    """Render a consistent page header."""
    st.markdown(f"""
    <div class="nv-fade-in" style="margin-bottom: 24px;">
        <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 12px;">
            {icon} {title}
        </h1>
        {f'<p style="margin: 8px 0 0; color: var(--text-secondary); font-size: 15px;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, action: str = None, action_key: str = None):
    """Render a section header with optional action button."""
    cols = st.columns([1, 1] if action else [1])
    with cols[0]:
        st.markdown(f"""
        <h2 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--text-primary);">
            {title}
        </h2>
        """, unsafe_allow_html=True)
    if action and action_key:
        with cols[1]:
            st.button(action, key=action_key, type="secondary")


def render_disclaimer():
    """Render disclaimer banner."""
    st.markdown("""
    <div style="
        background: var(--warning-light);
        border: 1px solid var(--warning);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 16px 0;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    ">
        <span style="font-size: 18px; flex-shrink: 0;">⚠️</span>
        <div style="flex: 1; color: var(--text-secondary); font-size: 13px; line-height: 1.5;">
            <strong style="color: var(--text-primary);">Educational Research Tool</strong> — 
            Not investment advice. No SEBI registration. 
            All signals are computational outputs — verify independently before acting.
        </div>
    </div>
    """, unsafe_allow_html=True)


def nv_card(title: str = None, content: str = None, **kwargs):
    """Render a styled card container."""
    title_html = f'<div style="font-weight: 600; font-size: 16px; color: var(--text-primary); margin-bottom: 12px;">{title}</div>' if title else ""
    content_html = content or ""
    style_str = ' '.join(f'{k}: {v};' for k, v in kwargs.items())
    st.markdown(f"""
    <div class="nv-card" style="padding: 20px; {style_str}">
        {title_html}
        {content_html}
    </div>
    """, unsafe_allow_html=True)