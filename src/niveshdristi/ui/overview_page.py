"""Fund Overview page (NEW, P8-S5) — KPI ribbon, positions, change feed,
needs attention. Verdict first, evidence behind expanders."""

from __future__ import annotations

import streamlit as st


def render_fund_overview(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        footer_strip,
        kpi_card,
        legend,
        unavailable_panel,
        why_expander,
    )

    banner_strip(payload)
    st.subheader("Fund overview")
    kpis = payload.get("kpis")
    if not kpis:
        empty_state("no sessions yet — run `nd paper tick`")
        footer_strip(payload, labels)
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Fund value (last close)", kpis["fund_value"])
    with c2:
        kpi_card("Last-session net P&L", kpis["net_pnl_session"],
                 "gross shown separately")
    with c3:
        kpi_card("Last-session gross P&L", kpis["gross_pnl_session"],
                 "before fees and slippage")

    legend()

    st.subheader("Positions")
    rows = payload.get("positions_view", [])
    if not rows:
        empty_state("no open positions")
    else:
        for row in rows:
            symbol = row["symbol"]
            signals = payload.get("signals", {}).get(symbol, {})
            lean = signals.get("lean", "No opinion")
            conv = signals.get("conviction")
            line = (f"{symbol} — {lean} — "
                    f"Conviction (uncalibrated, -1 to +1): "
                    f"{conv if conv is not None else 'n/a'}")
            with st.container(border=True):
                st.text(line)
                if row["last_close"] is not None and row["avg_cost"]:
                    pct = (row["last_close"] - row["avg_cost"]) / row["avg_cost"]
                    st.caption(f"unrealised: {pct * 100:.1f}%")
                else:
                    st.caption("unrealised: n/a")
                if signals.get("thesis"):
                    why_expander(thesis=signals["thesis"],
                                 evidence={"horizon_days": signals.get("horizon")})

    st.subheader("Sector & benchmark comparison")
    unavailable_panel("sector map and benchmark comparison")

    st.subheader("What changed in the last session")
    feed = payload.get("change_feed", [])
    if not feed:
        empty_state("no events recorded")
    for e in feed:
        st.text(f"{e['event']}: {e['detail']}")

    st.subheader("Needs attention")
    for item in payload.get("needs_attention", []):
        st.text(f"• {item}")
    footer_strip(payload, labels)
