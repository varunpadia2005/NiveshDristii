"""Orders / Activity page (P18-UI-S3e).

Fills and pending gated orders from the ledger/broker cache: resolved
display name, side, quantity, price, costs (fees/slippage when modeled;
the US COSTS NOT MODELED banner stays prominent from the header),
timestamps. Filter by symbol and side.
"""

from __future__ import annotations

import streamlit as st


def render_orders(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        fmt_money,
        footer_strip,
        section_header,
    )
    from niveshdristi.ui.names import display_name, display_tag

    banner_strip(payload)
    section_header("Orders / Activity",
                   "fills and pending gated orders from the ledger and "
                   "broker cache — nothing estimated")
    currency = labels.get("currency_code", "")

    from niveshdristi.services.paper_detail import orders_view

    view = orders_view(payload.get("fund_id", ""),
                       base=payload.get("fund_base"))
    fills = list(view.get("fills") or [])
    symbols = sorted({f["symbol"] for f in fills})
    sides = sorted({str(f.get("side", "")).upper() for f in fills})

    col1, col2 = st.columns(2)
    sym_filter = col1.selectbox("Symbol", ["(all)"] + symbols)
    side_filter = col2.selectbox("Side", ["(all)"] + sides)

    shown = [f for f in fills
             if (sym_filter == "(all)" or f["symbol"] == sym_filter)
             and (side_filter == "(all)"
                  or str(f.get("side", "")).upper() == side_filter)]

    tab_fills, tab_pending = st.tabs(["Fills", "Pending"])
    with tab_fills:
        st.caption(f"{len(shown)} of {len(fills)} fill(s)")
        if shown:
            rows = []
            for f in shown:
                name = display_name(f["symbol"])
                if display_tag(f["symbol"]):
                    name += " *"
                costs = ""
                if f.get("fees") is not None or f.get("slippage") is not None:
                    costs = (f"fees {fmt_money(f.get('fees'), currency)}, "
                             f"slippage {fmt_money(f.get('slippage'), currency)}")
                else:
                    costs = "costs not modeled"
                rows.append({
                    "Name": name,
                    "Ticker": f["symbol"],
                    "Side": str(f.get("side", "")).upper(),
                    "Qty": f"{f.get('quantity') or 0:,}",
                    "Price": fmt_money(f.get("price"), currency),
                    "Costs": costs,
                    "Session": str(f.get("session_date", "")),
                })
            st.dataframe(rows, hide_index=True, width="stretch")
            st.caption("* synthetic demo data")
        else:
            empty_state("no fills match this filter",
                        "clear the filters or run `nd paper tick`")
    with tab_pending:
        gated = view.get("pending_gated") or {}
        weights = gated.get("weights") or {}
        if weights:
            for sym in sorted(weights):
                name = display_name(sym)
                st.text(f"{name} ({sym}) — target weight "
                        f"{weights[sym]:.2f} — pending gate review")
            gate_log = gated.get("log") or []
            for g in gate_log:
                st.caption(f"gate {g.get('gate')}: {g.get('outcome')} "
                           f"({g.get('reason')})")
        else:
            st.caption("no pending gated orders")
    footer_strip(payload, labels)
