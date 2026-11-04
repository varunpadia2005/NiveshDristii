"""Deep-Dive page: Single stock analysis with Groww-inspired design."""
import streamlit as st
import pandas as pd
import asyncio
from niveshdristi.config import CFG
from niveshdristi.app.components import (
    page_header, render_disclaimer, metric_card, signal_badge,
    candle_chart, gauge_chart, signal_breakdown_chart, conviction_gauge,
    analyst_note_card, sector_quadrant_chart, regime_indicator,
    quick_stats_row, empty_state, tag
)


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()

    # Ticker selector with search
    universe = api_get("/universe/default")
    tickers = universe.get("tickers", []) if universe else []

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.selectbox(
            "Select Stock",
            tickers,
            index=0,
            format_func=lambda x: x,
            placeholder="Search for a stock...",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("\U0001f504 Refresh", key="refresh_deep", type="secondary", use_container_width=True):
            st.rerun()

    if not ticker:
        empty_state("\U0001f50d", "Select a Stock", "Choose a stock from the dropdown to begin analysis")
        return

    # Load all data with spinner
    with st.spinner(f"Loading {ticker} analysis..."):
        sig_data = api_get(f"/signal/{ticker}")
        px_data = api_get(f"/price/{ticker}")
        fund_data = api_get(f"/fundamentals/{ticker}")
        regime_data = api_get("/regime")

        # Load full price data for charts
        from niveshdristi.data.loader import load_prices
        from niveshdristi.indicators import compute_all_indicators
        from niveshdristi.signals import generate_signal_report

        price_data = asyncio.run(load_prices(ticker))
        df = compute_all_indicators(price_data.df)
        signal = generate_signal_report(ticker, df)

    if not sig_data:
        st.error(f"Failed to load data for {ticker}")
        return

    # Header with key metrics
    composite = sig_data.get("composite", 0)
    price = px_data.get("last_price", 0) if px_data else 0

    # Top bar with ticker, price, signal
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px;">
            <h1 style="margin: 0; font-size: 28px; font-weight: 700;">{ticker}</h1>
            <span style="font-size: 14px; color: var(--text-secondary);">{fund_data.get('fundamentals', {{}}).get('sector', 'N/A') if fund_data else 'N/A'}</span>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        metric_card("Price", f"\u20b9{price:,.1f}", icon="\U0001f4b0")

    with col3:
        # Signal badge
        signal_html = signal_badge(composite, f"{composite:.2f}")
        st.markdown(f"""
        <div class="nv-metric">
            <div class="nv-metric-label">Signal</div>
            <div class="nv-metric-value">{signal_html}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        metric_card("Conviction", f"{min(100, int(50 + 50 * composite))}/100", icon="\U0001f3af")

    st.markdown("<br>", unsafe_allow_html=True)

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "\U0001f4c8 Chart & Signals",
        "\U0001f4ca Fundamentals",
        "\U0001f30d Market Regime",
        "\U0001f916 AI Analyst",
        "\U0001f4c8 Price Ranges"
    ])

    # Tab 1: Chart & Signals
    with tab1:
        from niveshdristi.app.components import candle_chart, gauge_chart, signal_breakdown_chart

        # Chart
        st.plotly_chart(
            candle_chart(df, ticker, emas=[20, 50, 200], height=500),
            use_container_width=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Signal gauges
        st.markdown("### Signal Components")
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.plotly_chart(gauge_chart(sig_data.get("trend_score", 0), "Trend"), use_container_width=True)
        with g2:
            st.plotly_chart(gauge_chart(sig_data.get("momentum_score", 0), "Momentum"), use_container_width=True)
        with g3:
            st.plotly_chart(gauge_chart(sig_data.get("volatility_score", 0), "Vol Stretch"), use_container_width=True)
        with g4:
            st.plotly_chart(gauge_chart(sig_data.get("volume_score", 0), "Volume"), use_container_width=True)

        # Signal breakdown chart
        st.plotly_chart(
            signal_breakdown_chart(sig_data),
            use_container_width=True
        )

        # Signal reasons
        with st.expander("\U0001f4cb Signal Reasons", expanded=False):
            for reason in sig_data.get("reasons", []):
                st.markdown(f"\u2022 {reason}")

    # Tab 2: Fundamentals
    with tab2:
        if fund_data:
            fund = fund_data.get("fundamentals", {})
            guard = fund_data.get("guardrails", {})

            # Key metrics row
            st.markdown("### Key Metrics")
            stats = [
                {"label": "P/E Ratio", "value": f"{fund.get('pe_ratio', 0):.1f}" if fund.get('pe_ratio') else "N/A", "icon": "\U0001f4ca"},
                {"label": "P/B Ratio", "value": f"{fund.get('pb_ratio', 0):.1f}" if fund.get('pb_ratio') else "N/A", "icon": "\U0001f4da"},
                {"label": "ROE", "value": f"{fund.get('roe', 0)*100:.1f}%" if fund.get('roe') else "N/A", "icon": "\U0001f4c8"},
                {"label": "Debt/Equity", "value": f"{fund.get('debt_to_equity', 0):.2f}" if fund.get('debt_to_equity') else "N/A", "icon": "\u2696\ufe0f"},
                {"label": "Profit Margin", "value": f"{fund.get('profit_margin', 0)*100:.1f}%" if fund.get('profit_margin') else "N/A", "icon": "\U0001f4b0"},
                {"label": "Revenue Growth", "value": f"{fund.get('revenue_growth', 0)*100:.1f}%" if fund.get('revenue_growth') else "N/A", "icon": "\U0001f4ca"},
            ]
            quick_stats_row(stats)

            st.markdown("<br>", unsafe_allow_html=True)

            # Guardrails
            if guard.get("flags"):
                st.markdown("### \u26a0\ufe0f Guardrail Flags")
                for flag in guard["flags"]:
                    severity_color = "#E84D4D" if flag["severity"] == "error" else "#F5A623" if flag["severity"] == "warn" else "#007AFF"
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-card); border: 1px solid var(--border-light); border-radius: 8px; margin: 8px 0;">
                        <span style="background: {severity_color}20; color: {severity_color}; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase;">{flag['severity']}</span>
                        <div style="flex: 1;">
                            <div style="font-weight: 500; color: var(--text-primary);">{flag['metric'].replace('_', ' ').title()}</div>
                            <div style="font-size: 13px; color: var(--text-secondary);">{flag['message']}</div>
                        </div>
                        <div style="font-family: monospace; font-size: 14px; font-weight: 600; color: var(--text-primary);">{flag['value']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            if guard.get("max_score_cap", 100) < 100:
                st.markdown(f"""
                <div style="background: var(--warning-light); border: 1px solid var(--warning); border-radius: 10px; padding: 16px; margin: 16px 0;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 20px;">\u26a0\ufe0f</span>
                        <div>
                            <div style="font-weight: 600; color: var(--text-primary);">Conviction Score Capped</div>
                            <div style="font-size: 13px; color: var(--text-secondary);">Maximum conviction score limited to {guard['max_score_cap']}/100 due to guardrail flags</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            empty_state("\U0001f4ca", "No Fundamentals", "Unable to load fundamental data")

    # Tab 3: Market Regime
    with tab3:
        if regime_data:
            regime_indicator(regime_data.get("market_state", "unknown"), regime_data.get("vix_level", 15))

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Sector Rotation (RRG)")

            if regime_data.get("sectors"):
                from niveshdristi.app.components import sector_quadrant_chart
                st.plotly_chart(
                    sector_quadrant_chart(regime_data["sectors"]),
                    use_container_width=True
                )

                # Sector table
                st.markdown("### Sector Quadrants")
                quad_data = []
                for sector, quad in regime_data["sectors"].items():
                    quad_colors = {
                        "Leading": ("\U0001f7e2", "#00B87C"),
                        "Weakening": ("\U0001f7e1", "#F5A623"),
                        "Lagging": ("\U0001f534", "#E84D4D"),
                        "Improving": ("\U0001f535", "#007AFF"),
                    }
                    icon, color = quad_colors.get(quad, ("\u26aa", "#888"))
                    quad_data.append({
                        "Sector": sector,
                        "Quadrant": f'<span style="color: {color}; font-weight: 600;">{icon} {quad}</span>',
                    })

                if quad_data:
                    df = pd.DataFrame(quad_data)
                    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                st.info("Sector data unavailable")
        else:
            empty_state("\U0001f30d", "No Regime Data", "Unable to load market regime data")

    # Tab 4: AI Analyst
    with tab4:
        st.markdown("### AI Research Analyst")
        st.markdown("Grounded analysis based on technical, fundamental, and regime data.")

        if st.button("\U0001f9e0 Generate AI Note", type="primary", use_container_width=True):
            with st.spinner("Analyzing..."):
                import requests
                try:
                    r = requests.post(f"http://localhost:8000/analyst/{ticker}", timeout=60)
                    if r.ok:
                        data = r.json()
                        note = data.get("note", {})

                        if data.get("validated"):
                            st.success("\u2705 Note validated against facts bundle")
                        else:
                            st.warning(f"\u26a0\ufe0f Validation issues: {data.get('errors', [])}")

                        from niveshdristi.app.components import analyst_note_card
                        analyst_note_card(note)
                    else:
                        st.error(f"API error: {r.status_code}")
                except Exception as e:
                    st.error(f"Failed to generate note: {e}")
        else:
            st.info("Click 'Generate AI Note' to create a grounded research summary")

    # Tab 5: Price Ranges (placeholder)
    with tab5:
        st.markdown("### Price Ranges & Levels")
        st.info("Price ranges, ATR bands, and support/resistance levels coming soon")

        # Quick ATR levels
        if sig_data:
            atr = df["atr"].iloc[-1] if "atr" in df.columns else 0
            price = df["adj_close"].iloc[-1]

            st.markdown("### ATR-Based Levels")
            cols = st.columns(4)
            for i, mult in enumerate([1, 2, 3]):
                with cols[i]:
                    upper = price + mult * atr
                    lower = price - mult * atr
                    st.markdown(f"""
                    <div class="nv-card" style="text-align: center; padding: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">{mult}x ATR</div>
                        <div style="font-size: 14px; font-weight: 600; color: var(--danger); margin: 4px 0;">\u20b9{upper:,.1f}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">Resistance</div>
                        <div style="height: 1px; background: var(--border-light); margin: 8px 0;"></div>
                        <div style="font-size: 14px; font-weight: 600; color: var(--success);">\u20b9{lower:,.1f}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">Support</div>
                    </div>
                    """, unsafe_allow_html=True)
