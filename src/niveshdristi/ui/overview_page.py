"""Fund Overview page (NEW, P8-S5) — KPI ribbon, positions, change feed,
needs attention. Verdict first, evidence behind expanders."""

from __future__ import annotations

import streamlit as st


def render_fund_overview(payload: dict, labels: dict) -> None:
    from niveshdristi.services.fund_overview import nav_series
    from niveshdristi.ui.components import (
        banner_strip,
        change_chip,
        empty_state,
        fmt_money,
        footer_strip,
        kpi_card,
        legend,
        section_header,
        unavailable_panel,
        why_expander,
    )

    def _nav_base(payload: dict) -> str | None:
        # fund_overview does not carry the base; read it the same way the
        # app shell does (session_state then env).

        return None  # nav_series resolves the base itself via env/session

    banner_strip(payload)

    fund_name = payload.get("fund_id", "")
    market_tag = (f"fund: {fund_name} · "
                  f"{labels.get('market_name', '')} · "
                  f"{labels.get('currency_code', '')}")
    section_header("Fund overview", market_tag)

    kpis = payload.get("kpis")
    if not kpis:
        empty_state("no sessions yet — run `nd paper tick`",
                    "generate a demo fund with tools/make_demo_fund.py")
        footer_strip(payload, labels)
        return
    nav = nav_series(payload.get("fund_id", ""),
                     base=payload.get("fund_base"))

    # Hero NAV card (P19-LOOK S3a): big number + change chip + mini NAV
    hero_l, hero_r = st.columns([2, 3])
    with hero_l.container(key="hero"):
        st.metric("Fund value (last close)", kpis["fund_value"])
        st.caption(f"{payload.get('records', 0)} sessions · ledger verify: "
                   f"{payload.get('verify', 'n/a')}")
        if payload.get("halted"):
            with st.container(key="haltpill"):
                st.caption(f"TRADING HALTED: "
                           f"{payload.get('halt_reason') or ''}")
        else:
            with st.container(key="statuspill"):
                st.caption("kill-switch: not halted")
    with hero_r.container(key="panel"):
        if len(nav) >= 2:
            start_equity, last_equity = (nav[0]["equity"],
                                         nav[-1]["equity"])
            prev_equity = nav[-2]["equity"]
            day_change = last_equity - prev_equity
            change_chip(round(day_change, 2))
            if start_equity:
                total_ret = ((last_equity - start_equity)
                             / start_equity * 100.0)
                word = ("up" if total_ret > 0
                        else "down" if total_ret < 0 else "flat")
                arrow = ("▲" if total_ret > 0
                         else "▼" if total_ret < 0 else "—")
                st.caption(
                    f"Total return since start: {arrow} {word} "
                    f"{total_ret:+.2f}% "
                    f"({fmt_money(last_equity - start_equity)}) "
                    "— pipeline demonstration only; not evidence of "
                    "performance"
                )
            import pandas as pd

            chart = pd.DataFrame(
                {"equity": [p["equity"] for p in nav]},
                index=[str(p["session"]) for p in nav],
            )
            st.line_chart(chart, height=200)
        else:
            empty_state("no NAV series yet — run `nd paper tick`")

    # KPI tiles row
    t1, t2, t3 = st.columns(3)
    with t1.container(key="tile_net"):
        kpi_card("Last-session net P&L", kpis["net_pnl_session"],
                 "gross shown separately")
    with t2.container(key="tile_gross"):
        kpi_card("Last-session gross P&L", kpis["gross_pnl_session"],
                 "before fees and slippage")
    with t3.container(key="tile_cash"):
        kpi_card("Cash", fmt_money(payload.get("cash"), ""),
                 f"ledger verify: {payload.get('verify', 'n/a')}")

    legend()

    legend()

    section_header("Positions")
    positions_count = len(payload.get("positions_view", []))
    st.caption(f"{positions_count} position(s)")

    rows = payload.get("positions_view", [])
    if not rows:
        empty_state("no open positions")
    else:
        for row in rows:
            symbol = row["symbol"]
            signals = payload.get("signals", {}).get(symbol, {})
            lean = signals.get("lean", "No opinion")
            conv = signals.get("conviction")
            from niveshdristi.ui.names import display_name

            line = (f"{display_name(symbol)} ({symbol}) — {lean} — "
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
