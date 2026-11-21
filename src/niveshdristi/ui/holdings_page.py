"""Holdings / Portfolio page (P18-UI-S3d).

A table of holdings — resolved display name, quantity, avg cost, last
price, value, unrealised P&L (arrow + word + number; 'n/a (no avg cost
recorded)' when the entry was at creation) and weights — with a totals
row. Every number is ledger/snapshot-derived via
services.fund_overview.holdings_view.
"""

from __future__ import annotations

import streamlit as st


def render_holdings(payload: dict, labels: dict) -> None:
    from niveshdristi.services.fund_overview import holdings_view
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        fmt_money,
        fmt_pct,
        footer_strip,
        section_header,
    )
    from niveshdristi.ui.names import display_name, display_tag

    banner_strip(payload)
    section_header("Holdings",
                   "every number from the ledger and stored snapshots — "
                   "no estimates")
    view = holdings_view(payload.get("fund_id", ""),
                         base=payload.get("fund_base"))
    rows = view.get("rows", [])
    currency = labels.get("currency_code", "")
    if not rows:
        empty_state("no holdings recorded",
                    "run `nd paper tick` or generate a demo fund")
        footer_strip(payload, labels)
        return

    table_rows = []
    for r in rows:
        name = display_name(r["symbol"])
        if display_tag(r["symbol"]):
            name += " *"
        if r["pnl_amount"] is not None:
            word = "up" if r["pnl_amount"] > 0 else \
                "down" if r["pnl_amount"] < 0 else "flat"
            arrow = "▲" if r["pnl_amount"] > 0 else \
                "▼" if r["pnl_amount"] < 0 else "—"
            pnl = f"{arrow} {word} {fmt_money(r['pnl_amount'], currency)} " \
                  f"({fmt_pct(r['pnl_pct'])})"
        else:
            pnl = "n/a (no avg cost recorded)"
        table_rows.append({
            "Name": name,
            "Ticker": r["symbol"],
            "Qty": f"{r['quantity']:,}",
            "Avg cost": fmt_money(r["avg_cost"], currency)
            if r["avg_cost"] is not None else "—",
            "Last price": fmt_money(r["last_close"], currency),
            "Value": fmt_money(r["value"], currency)
            if r["value"] is not None else "—",
            "Unrealised P&L": pnl,
            "Weight": fmt_pct((r["weight_pct"] or 0) / 100.0)
            if r["weight_pct"] is not None else "—",
        })
    st.dataframe(table_rows, hide_index=True, width="stretch")
    st.caption("* synthetic demo data")
    st.caption(f"Total value: {fmt_money(view.get('total_value'), currency)}"
               f" · as-of: {view.get('as_of')}")
    footer_strip(payload, labels)
