"""Shared Streamlit components - Groww-inspired."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from niveshdristi.app.theme import page_header, section_header, render_disclaimer


def metric_card(label: str, value: str, change: str = None, change_type: str = "neutral", 
                icon: str = "", help_text: str = None):
    """Render a metric card with optional change indicator."""
    change_class = {"positive": "nv-change-positive", "negative": "nv-change-negative", "neutral": "nv-change-neutral"}.get(change_type, "nv-change-neutral")
    change_html = f'<div class="nv-metric-change {change_class}">{change}</div>' if change else ""
    icon_html = f'<span style="font-size: 20px; margin-right: 8px;">{icon}</span>' if icon else ""
    
    help_attr = f' title="{help_text}"' if help_text else ""
    
    st.markdown(f"""
    <div class="nv-metric"{help_attr}>
        <div class="nv-metric-label">{icon_html}{label}</div>
        <div class="nv-metric-value">{value}</div>
        {change_html}
    </div>
    """, unsafe_allow_html=True)


def signal_badge(score: float, label: str = None) -> str:
    """Return HTML badge for signal score."""
    if score > 0.2:
        cls = "positive"
        text = "Bullish"
        dot = "🟢"
    elif score < -0.2:
        cls = "negative"
        text = "Bearish"
        dot = "🔴"
    else:
        cls = "neutral"
        text = "Neutral"
        dot = "🟡"
    
    label_html = f" {label}" if label else ""
    return f'<span class="nv-badge {cls}">{dot} {text}{label_html}</span>'


def candle_chart(df: pl.DataFrame, ticker: str, emas: list = None, height: int = 500,
                 volume: bool = True, indicators: list = None) -> go.Figure:
    """Create an interactive candlestick chart with volume."""
    pdf = df.to_pandas()
    emas = emas or [20, 50, 200]
    
    # Create subplots
    rows = 2 if volume else 1
    row_heights = [0.7, 0.3] if volume else [1]
    
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=pdf["date"],
        open=pdf["adj_open"],
        high=pdf["adj_high"],
        low=pdf["adj_low"],
        close=pdf["adj_close"],
        name="Price",
        increasing_line_color="#00B87C",
        decreasing_line_color="#E84D4D",
        increasing_fillcolor="#00B87C",
        decreasing_fillcolor="#E84D4D",
    ), row=1, col=1)
    
    # EMAs
    colors = {"20": "#007AFF", "50": "#F5A623", "200": "#AF52DE"}
    for p in emas:
        col = f"ema_{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=pdf["date"], y=pdf[col],
                name=f"EMA {p}",
                line=dict(color=colors.get(str(p), "#888"), width=1.5),
                opacity=0.8,
                hovertemplate=f"EMA {p}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)
    
    # Indicators overlay
    if indicators:
        for ind in indicators:
            if ind in df.columns:
                fig.add_trace(go.Scatter(
                    x=pdf["date"], y=pdf[ind],
                    name=ind,
                    line=dict(width=1, dash='dot'),
                    opacity=0.6,
                ), row=1, col=1)
    
    # Volume
    if volume and "volume" in df.columns:
        colors_vol = ["#E84D4D" if c < o else "#00B87C" 
                      for c, o in zip(pdf["adj_close"], pdf["adj_open"])]
        fig.add_trace(go.Bar(
            x=pdf["date"], y=pdf["volume"],
            name="Volume",
            marker_color=colors_vol,
            opacity=0.7,
            hovertemplate="Volume: %{y:,.0f}<extra></extra>",
        ), row=2, col=1)
    
    # Layout
    theme = st.session_state.get("theme", "light")
    is_dark = theme == "dark"
    
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11)
        ),
        hovermode="x unified",
        xaxis=dict(
            showgrid=True,
            gridcolor="var(--chart-grid)" if not is_dark else "#21262D",
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="var(--chart-grid)" if not is_dark else "#21262D",
            zeroline=False,
            side="right",
        ),
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=11),
    )
    
    if volume:
        fig.update_yaxes(title_text="Price (₹)", row=1, col=1, side="right")
        fig.update_yaxes(title_text="Vol", row=2, col=1, side="right", showgrid=False)
        fig.update_xaxes(row=2, col=1, showgrid=False)
    else:
        fig.update_yaxes(title_text="Price (₹)", side="right")
    
    return fig


def gauge_chart(score: float, title: str, height: int = 160) -> go.Figure:
    """Create a gauge chart for signal scores."""
    color = "#00B87C" if score > 0.2 else "#E84D4D" if score < -0.2 else "#F5A623"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 13, 'color': 'var(--text-secondary)'}},
        number={'font': {'size': 28, 'color': 'var(--text-primary)'}, 'valueformat': '.2f'},
        gauge={
            'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': 'var(--text-muted)'},
            'bar': {'color': color, 'thickness': 0.25},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 1,
            'bordercolor': "var(--border-light)",
            'steps': [
                {'range': [-1, -0.2], 'color': "#E84D4D30"},
                {'range': [-0.2, 0.2], 'color': "#F5A62330"},
                {'range': [0.2, 1], 'color': "#00B87C30"},
            ],
            'threshold': {
                'line': {'color': 'var(--text-primary)', 'width': 3},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif"),
    )
    return fig


def sparkline(data: List[float], color: str = None, height: int = 40) -> go.Figure:
    """Create a mini sparkline chart."""
    if color is None:
        color = "#00B87C" if data[-1] >= data[0] else "#E84D4D"
    
    fig = go.Figure(go.Scatter(
        x=list(range(len(data))),
        y=data,
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=f"{color}20",
        hovertemplate="%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x",
    )
    return fig


def stock_card(ticker: str, signal_data: dict, price_data: dict, fundamentals: dict = None) -> None:
    """Render a stock card in grid view."""
    composite = signal_data.get("composite", 0)
    price = price_data.get("last_price", 0) if price_data else 0
    
    signal_cls = "positive" if composite > 0.2 else "negative" if composite < -0.2 else "neutral"
    signal_text = "Bullish" if composite > 0.2 else "Bearish" if composite < -0.2 else "Neutral"
    signal_icon = "🟢" if composite > 0.2 else "🔴" if composite < -0.2 else "🟡"
    signal_color = "var(--success)" if composite > 0.2 else "var(--danger)" if composite < -0.2 else "var(--warning)"
    
    pe = fundamentals.get("pe_ratio") if fundamentals else None
    roe = fundamentals.get("roe") if fundamentals else None
    
    with st.container():
        st.markdown(f"""
        <div class="nv-card nv-fade-in" style="padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div>
                    <div style="font-size: 16px; font-weight: 600; color: var(--text-primary);">{ticker}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">{signal_icon} {signal_text}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 20px; font-weight: 700; color: var(--text-primary);">₹{price:,.1f}</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Composite: {composite:.2f}</div>
                </div>
            </div>
            <div style="display: flex; gap: 16px; padding-top: 12px; border-top: 1px solid var(--border-light);">
                <div style="flex: 1;">
                    <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">P/E</div>
                    <div style="font-size: 14px; font-weight: 600; color: var(--text-primary);">{f"{pe:.1f}" if pe else "N/A"}</div>
                </div>
                <div style="flex: 1;">
                    <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">ROE</div>
                    <div style="font-size: 14px; font-weight: 600; color: var(--text-primary);">{f"{roe*100:.1f}%" if roe else "N/A"}</div>
                </div>
                <div style="flex: 1; text-align: right;">
                    <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Signal</div>
                    <div style="font-size: 14px; font-weight: 600; color: {signal_color};">{signal_text}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def conviction_gauge(score: int, components: dict) -> None:
    """Render conviction score with component breakdown."""
    # Main score
    color = "#00B87C" if score >= 70 else "#F5A623" if score >= 50 else "#E84D4D"
    
    st.markdown(f"""
    <div class="nv-card" style="text-align: center; padding: 24px;">
        <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
            Conviction Score
        </div>
        <div style="font-size: 56px; font-weight: 700; color: {color}; line-height: 1; margin-bottom: 4px;">
            {score}
        </div>
        <div style="font-size: 14px; color: var(--text-secondary); margin-bottom: 24px;">
            /100
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Component breakdown
    cols = st.columns(len(components))
    for i, (name, value) in enumerate(components.items()):
        with cols[i]:
            comp_color = "#00B87C" if value >= 70 else "#F5A623" if value >= 50 else "#E84D4D"
            st.markdown(f"""
            <div class="nv-card" style="text-align: center; padding: 16px;">
                <div style="font-size: 11px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">
                    {name.title()}
                </div>
                <div style="font-size: 24px; font-weight: 700; color: {comp_color};">
                    {value}
                </div>
            </div>
            """, unsafe_allow_html=True)


def signal_breakdown_chart(signal_data: dict) -> go.Figure:
    """Create a horizontal bar chart for signal components."""
    components = signal_data.get("components", {})
    if not components:
        return go.Figure()
    
    names = list(components.keys())
    values = list(components.values())
    colors = ["#00B87C" if v > 0 else "#E84D4D" if v < 0 else "#F5A623" for v in values]
    
    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation='h',
        marker_color=colors,
        text=[f"{v:.2f}" for v in values],
        textposition='outside',
        textfont=dict(size=11, color='var(--text-primary)'),
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    ))
    
    fig.update_layout(
        height=200,
        margin=dict(l=80, r=30, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            range=[-1.1, 1.1],
            showgrid=True,
            gridcolor="var(--chart-grid)",
            zeroline=True,
            zerolinecolor="var(--border-light)",
            zerolinewidth=1,
            showticklabels=False,
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickfont=dict(size=11, color='var(--text-primary)'),
        ),
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=11),
    )
    
    # Add zero line
    fig.add_vline(x=0, line_color="var(--border-medium)", line_width=1, line_dash="dash")
    
    return fig


def regime_indicator(state: str, vix: float) -> None:
    """Render regime indicator with VIX."""
    state_colors = {
        "bull": ("#00B87C", "🟢", "Bull Market"),
        "bear": ("#E84D4D", "🔴", "Bear Market"),
        "choppy": ("#F5A623", "🟡", "Choppy/Sideways"),
        "unknown": ("#888", "⚪", "Unknown"),
    }
    color, icon, label = state_colors.get(state.lower(), state_colors["unknown"])
    
    st.markdown(f"""
    <div class="nv-card" style="display: flex; align-items: center; gap: 16px; padding: 16px;">
        <div style="font-size: 32px;">{icon}</div>
        <div>
            <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">{label}</div>
            <div style="font-size: 13px; color: var(--text-secondary);">India VIX: {vix:.1f}</div>
        </div>
        <div style="margin-left: auto; text-align: right;">
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Fear Index</div>
            <div style="font-size: 20px; font-weight: 700; color: {color};">{vix:.1f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def sector_quadrant_chart(quadrants: dict) -> go.Figure:
    """Create RRG quadrant scatter plot."""
    # Quadrant positions
    quad_positions = {
        "Leading": (1, 1),
        "Weakening": (-1, 1),
        "Lagging": (-1, -1),
        "Improving": (1, -1),
    }
    colors = {
        "Leading": "#00B87C",
        "Weakening": "#F5A623",
        "Lagging": "#E84D4D",
        "Improving": "#007AFF",
    }
    
    fig = go.Figure()
    
    # Add quadrant backgrounds
    fig.add_shape(type="rect", x0=0, y0=0, x1=1, y1=1,
                  fillcolor="#00B87C15", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-1, y0=0, x1=0, y1=1,
                  fillcolor="#F5A62315", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-1, y0=-1, x1=0, y1=0,
                  fillcolor="#E84D4D15", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=0, y0=-1, x1=1, y1=0,
                  fillcolor="#007AFF15", line_width=0, layer="below")
    
    # Add sector points
    for sector, quad in quadrants.items():
        if quad in quad_positions:
            x, y = quad_positions[quad]
            # Add some jitter
            x += np.random.uniform(-0.15, 0.15)
            y += np.random.uniform(-0.15, 0.15)
            
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode="markers+text",
                text=[sector],
                textposition="top center",
                textfont=dict(size=10, color="var(--text-primary)"),
                marker=dict(
                    size=14,
                    color=colors.get(quad, "#888"),
                    line=dict(width=2, color="white"),
                ),
                name=quad,
                showlegend=False,
                hovertemplate=f"{sector}<br>Quadrant: {quad}<extra></extra>",
            ))
    
    fig.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[-1.3, 1.3], showgrid=True, gridcolor="var(--chart-grid)", 
                   zeroline=True, zerolinecolor="var(--border-light)", showticklabels=False),
        yaxis=dict(range=[-1.3, 1.3], showgrid=True, gridcolor="var(--chart-grid)", 
                   zeroline=True, zerolinecolor="var(--border-light)", showticklabels=False),
        showlegend=False,
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=11),
    )
    
    return fig


def analyst_note_card(note: dict) -> None:
    """Render analyst note with structured sections."""
    st.markdown(f"""
    <div class="nv-card nv-fade-in" style="padding: 20px;">
        <div style="font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 12px;">
            📝 Research Summary
        </div>
        <div style="color: var(--text-primary); line-height: 1.6; margin-bottom: 20px;">
            {note.get('summary', '')}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Two column layout for bull/bear
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="nv-card" style="padding: 16px; border-left: 3px solid var(--success);">
            <div style="font-size: 12px; font-weight: 600; color: var(--success); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                🟢 Bull Case
            </div>
        """, unsafe_allow_html=True)
        for item in note.get("bull_case", []):
            st.markdown(f'<div style="margin: 8px 0; padding-left: 16px; border-left: 2px solid var(--success-light); color: var(--text-primary); font-size: 13px; line-height: 1.5;">• {item}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="nv-card" style="padding: 16px; border-left: 3px solid var(--danger);">
            <div style="font-size: 12px; font-weight: 600; color: var(--danger); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                🔴 Bear Case
            </div>
        """, unsafe_allow_html=True)
        for item in note.get("bear_case", []):
            st.markdown(f'<div style="margin: 8px 0; padding-left: 16px; border-left: 2px solid var(--danger-light); color: var(--text-primary); font-size: 13px; line-height: 1.5;">• {item}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Risks and catalysts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="nv-card" style="padding: 16px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--warning); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                ⚠️ Key Risks
            </div>
        """, unsafe_allow_html=True)
        for item in note.get("risks", []):
            st.markdown(f'<div style="margin: 6px 0; font-size: 13px; color: var(--text-primary);">• {item}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="nv-card" style="padding: 16px;">
            <div style="font-size: 12px; font-weight: 600; color: var(--info); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                🔄 Would Change View
            </div>
        """, unsafe_allow_html=True)
        for item in note.get("would_change_view", []):
            st.markdown(f'<div style="margin: 6px 0; font-size: 13px; color: var(--text-primary);">• {item}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def watchlist_table(stocks: List[Dict], on_select: callable = None) -> Optional[str]:
    """Render interactive watchlist table."""
    if not stocks:
        st.info("No stocks in watchlist")
        return None
    
    df = pd.DataFrame(stocks)
    
    # Configure columns
    column_config = {
        "ticker": st.column_config.TextColumn("Symbol", width="small"),
        "name": st.column_config.TextColumn("Name", width="medium"),
        "price": st.column_config.NumberColumn("Price (₹)", format="₹%.2f", width="small"),
        "change": st.column_config.NumberColumn("Change %", format="%.2f%%", width="small"),
        "signal": st.column_config.TextColumn("Signal", width="small"),
        "composite": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "pe": st.column_config.NumberColumn("P/E", format="%.1f", width="small"),
        "roe": st.column_config.NumberColumn("ROE %", format="%.1f%%", width="small"),
        "sector": st.column_config.TextColumn("Sector", width="small"),
    }
    
    # Display with selection
    event = st.dataframe(
        df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun" if on_select else "ignore",
        selection_mode="single-row",
    )
    
    if on_select and event.selection.rows:
        return df.iloc[event.selection.rows[0]]["ticker"]
    return None


def quick_stats_row(stats: List[Dict]) -> None:
    """Render a row of quick stat cards."""
    cols = st.columns(len(stats))
    for i, stat in enumerate(stats):
        with cols[i]:
            metric_card(
                stat.get("label", ""),
                stat.get("value", ""),
                stat.get("change"),
                stat.get("change_type", "neutral"),
                stat.get("icon", ""),
                stat.get("help"),
            )


def empty_state(icon: str, title: str, message: str, action_label: str = None, action_key: str = None) -> None:
    """Render an empty state with optional action."""
    st.markdown(f"""
    <div style="text-align: center; padding: 60px 20px; background: var(--bg-secondary); border-radius: 16px; border: 1px dashed var(--border-light);">
        <div style="font-size: 48px; margin-bottom: 16px;">{icon}</div>
        <h3 style="margin: 0 0 8px; color: var(--text-primary); font-size: 20px;">{title}</h3>
        <p style="margin: 0; color: var(--text-secondary); font-size: 15px;">{message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if action_label and action_key:
        st.button(action_label, key=action_key, type="primary", use_container_width=True)


def loading_skeleton(count: int = 3) -> None:
    """Render skeleton loading placeholders."""
    cols = st.columns(count)
    for col in cols:
        with col:
            st.markdown("""
            <div class="nv-card" style="padding: 16px;">
                <div style="height: 20px; background: linear-gradient(90deg, var(--border-light) 25%, var(--border-medium) 50%, var(--border-light) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; margin-bottom: 12px;"></div>
                <div style="height: 32px; background: linear-gradient(90deg, var(--border-light) 25%, var(--border-medium) 50%, var(--border-light) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; margin-bottom: 8px;"></div>
                <div style="height: 16px; background: linear-gradient(90deg, var(--border-light) 25%, var(--border-medium) 50%, var(--border-light) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; width: 60%;"></div>
            </div>
            <style>
            @keyframes shimmer {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
            </style>
            """, unsafe_allow_html=True)


def tooltip(text: str) -> str:
    """Return HTML for a tooltip icon."""
    return f'<span style="cursor: help; color: var(--text-muted); font-size: 12px; margin-left: 4px;" title="{text}">ⓘ</span>'


def tag(text: str, color: str = "info") -> str:
    """Render a colored tag."""
    colors = {
        "success": ("var(--success-light)", "var(--success)"),
        "danger": ("var(--danger-light)", "var(--danger)"),
        "warning": ("var(--warning-light)", "var(--warning)"),
        "info": ("var(--info-light)", "var(--info)"),
        "neutral": ("var(--bg-secondary)", "var(--text-secondary)"),
    }
    bg, fg = colors.get(color, colors["info"])
    return f'<span style="background: {bg}; color: {fg}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;">{text}</span>'


def copy_button(text: str, label: str = "Copy", key: str = None) -> None:
    """Render a copy-to-clipboard button."""
    if st.button(label, key=key):
        st.code(text, language=None)
        st.toast("Copied to clipboard!")


def expandable_section(title: str, content: str, expanded: bool = False) -> None:
    """Render an expandable section with custom styling."""
    with st.expander(title, expanded=expanded):
        st.markdown(content)


def tabs_container(tabs: List[tuple], render_func: callable) -> None:
    """Render tabs with custom content."""
    tab_labels = [t[0] for t in tabs]
    tab_keys = [t[1] for t in tabs]
    
    selected = st.tabs(tab_labels)
    for i, tab in enumerate(selected):
        with tab:
            render_func(tab_keys[i])


# Utility for formatting
def fmt_inr(value: float) -> str:
    """Format number in Indian Rupee format."""
    if value >= 1e7:
        return f"₹{value/1e7:.2f} Cr"
    elif value >= 1e5:
        return f"₹{value/1e5:.2f} L"
    elif value >= 1e3:
        return f"₹{value/1e3:.2f} K"
    return f"₹{value:,.2f}"


def fmt_pct(value: float) -> str:
    """Format percentage with sign."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"