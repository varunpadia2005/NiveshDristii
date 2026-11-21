"""Backtest Lab page (NEW, P8-S8). Run over stored snapshots; verdict first
with the FIXED wording; drag split into fees and slippage."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def render_backtest_lab(payload: dict, labels: dict) -> None:
    from niveshdristi.services.backtest_lab import content_key, run_backtest_service
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        fmt_money,
        footer_strip,
        section_header,
        unavailable_panel,
    )

    banner_strip(payload)
    section_header("Backtest lab",
                   "runs the engine over the fund's STORED snapshots — no "
                   "network, no refetch. Results are a pipeline "
                   "demonstration only; not evidence of performance.")
    if not payload.get("records"):
        empty_state("no stored sessions — nothing to run")
        footer_strip(payload, labels)
        return
    if st.button("Run backtest", key="run_backtest_btn"):
        key = content_key(payload["fund_id"],
                          st.session_state.get("fund_base"))
        result = run_backtest_service(payload["fund_id"],
                                      st.session_state.get("fund_base"),
                                      _key=key)
        if not result.get("available"):
            empty_state(result.get("reason", "unavailable"))
        else:
            st.metric("Verdict", result["verdict"])
            st.caption(f"promotable flag on this data: "
                       f"{result['promotable']} (always False on this data)")
            st.caption("drag = slippage + fees measured in NAV basis points; "
                       "the green/red arrow convention is ▲ favourable, "
                       "▼ unfavourable")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[d for d, _ in result["net_curve"]],
                y=[v for _, v in result["net_curve"]],
                name="net (after fees+slippage)"))
            fig.add_trace(go.Scatter(
                x=[d for d, _ in result["gross_curve"]],
                y=[v for _, v in result["gross_curve"]],
                name="gross (before frictions)"))
            fig.update_layout(template="plotly_white", height=380,
                              margin={"l": 10, "r": 10, "t": 10, "b": 10})
            st.plotly_chart(fig, use_container_width=True)
            currency = labels.get("currency_code", "")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("drag (NAV bps)", result["drag_bps"])
            c2.metric("fees", fmt_money(result["fees_total"], currency))
            c3.metric("slippage", fmt_money(result["slippage_total"],
                                            currency))
            c4.metric("trades", result["trade_count"])
            st.caption(f"calendar source: {result['calendar_source']}")
            st.text("DataLimitations: " + ", ".join(result["limitations"]))
    unavailable_panel("TrialRecorder summary across many parameter trials")
    footer_strip(payload, labels)
