"""Stock Deep-Dive + Compare pages (NEW, P8-S7). Plotly charts; everything
from stored snapshots; no action buttons."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _candlestick(payload: dict) -> None:
    candles = payload["candles"]
    fig = go.Figure(data=[go.Candlestick(
        x=[c["date"] for c in candles],
        open=[c["open"] for c in candles] if "open" in candles[0]
        else [c["close"] for c in candles],
        high=[c.get("adj_high", c.get("high", c["close"])) for c in candles],
        low=[c.get("adj_low", c.get("low", c["close"])) for c in candles],
        close=[c.get("adj_close", c["close"]) for c in candles],
    )])
    fig.update_layout(template="plotly_white", height=420,
                      margin={"l": 10, "r": 10, "t": 10, "b": 10})
    st.plotly_chart(fig, use_container_width=True)


def _indicator_panes(payload: dict) -> None:
    ind = payload["indicators"]
    c1, c2 = st.columns(2)
    c1.text(f"RSI: {ind['rsi'] if ind['rsi'] is not None else 'n/a'}")
    c2.text(f"MACD histogram: "
            f"{ind['macd_hist'] if ind['macd_hist'] is not None else 'n/a'}")
    st.text(f"50-day: {ind['ma50_position']} · 200-day: {ind['ma200_position']}")


def render_deep_dive(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        footer_strip,
        unavailable_panel,
        why_expander,
    )

    banner_strip(payload)
    from niveshdristi.ui.names import display_name, display_tag

    _sym = payload.get('symbol', '')
    st.subheader(f"Stock deep-dive: {display_name(_sym)} ({_sym})")
    if display_tag(_sym):
        st.caption(display_tag(_sym))
    if not payload.get("available"):
        empty_state(payload.get("reason", "unavailable"))
        footer_strip(payload, labels)
        return
    _candlestick(payload)
    _indicator_panes(payload)
    st.subheader("Entry / stop zones (evidence only)")
    zones = payload["zones_evidence_only"]
    st.text(f"support {zones['support']:.2f} · resistance "
            f"{zones['resistance']:.2f} · entry zone "
            f"{zones['entry_zone_low']:.2f}..{zones['entry_zone_high']:.2f} · "
            f"stop zone {zones['stop_zone']:.2f} (evidence-only, no opinion)")
    st.subheader("Per-model signals")
    for m in payload["per_model"]:
        st.text(f"{m['model_id']}: {m['label']}")
        if m.get("thesis"):
            why_expander(thesis=m["thesis"])
    st.subheader("Recorded risk-gate verdicts")
    if not payload["gate_log"]:
        st.caption("no recorded clamp entries for the last decision")
    for entry in payload["gate_log"]:
        st.text(f"{entry.get('gate', '?')} {entry.get('symbol', '')}: "
                f"{entry.get('outcome', '')} — {entry.get('reason', '')}")
    for item in payload["unavailable"]:
        unavailable_panel(item)
    footer_strip(payload, labels)


def render_compare(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import footer_strip, unavailable_panel

    # P19-LOOK: the page-level banner strip already rendered the mandatory
    # banners; repeating them here made a second warning element. The
    # disclaimer/footer still renders at the bottom of the page.
    st.subheader("Compare (side by side, no actions)")
    a, b = payload["a"], payload["b"]
    if not (a.get("available") and b.get("available")):
        unavailable_panel("compare")
        footer_strip(payload, labels)
        return
    col_a, col_b = st.columns(2)
    from niveshdristi.ui.names import display_name

    for col, side in ((col_a, a), (col_b, b)):
        with col:
            st.text(f"{display_name(side['symbol'])} ({side['symbol']})")
            _indicator_panes(side)
            for m in side["per_model"]:
                st.text(f"{m['model_id']}: {m['label']}")
            st.caption(f"recorded gate entries: {len(side['gate_log'])}")
    footer_strip(payload, labels)
