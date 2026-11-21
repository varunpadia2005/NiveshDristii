"""Market Overview + Signals Board pages (NEW, P8-S6)."""

from __future__ import annotations

import streamlit as st


def render_market_overview(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import (
        banner_strip,
        footer_strip,
        unavailable_panel,
    )

    banner_strip(payload)
    st.subheader("Market overview")
    st.metric("Last data session", payload["last_data_session"] or "n/a")
    st.caption(payload["holiday_note"])
    for item in payload["unavailable"]:
        unavailable_panel(item)
    footer_strip(payload, labels)


def render_signals_board(rows: list[dict], payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        footer_strip,
        legend,
        unavailable_panel,
        why_expander,
    )

    banner_strip(payload)
    st.subheader("Signals board")
    legend()
    c1, c2 = st.columns(2)
    min_conv = c1.slider(
        "Minimum |conviction| filter (uncalibrated)", 0.0, 1.0, 0.0, 0.1)
    search = c2.text_input("Instrument search", key="signal_search")
    sector = c2.selectbox("Sector filter", ["unavailable: no verified "
                                            "data source"])
    del sector  # displayed as unavailable, never functional

    if not rows:
        empty_state("no stored sessions — nothing to show")
        footer_strip(payload, labels)
        return
    for row in rows:
        if search and search.upper() not in row["symbol"]:
            continue
        if row["conviction"] is not None and abs(row["conviction"]) < min_conv:
            continue
        with st.container(border=True):
            from niveshdristi.ui.names import display_name

            st.text(f"{display_name(row['symbol'])} ({row['symbol']}) — {row['lean']} — "
                    f"{row['conviction_caption']}: "
                    f"{row['conviction'] if row['conviction'] is not None else 'n/a'}"
                    f" — horizon {row['horizon'] or 'n/a'}d — "
                    f"[{row['data_status']}]")
            if row["data_status"].startswith("Stub"):
                st.caption("Stub: not computed")
            why_expander(thesis=row["thesis"] or "(no thesis recorded)",
                         evidence={"last_volume": row["last_volume"]})
    unavailable_panel("sector filter")
    footer_strip(payload, labels)
