"""Stock detail page (P18-UI-S3c).

Display name + ticker + honest tags, price chart from the fund's stored
snapshot candles, per-model signals with their data_status, position
info if held, and recent fills for the symbol — all from repo services
(read_fund + deep_dive), nothing invented.
"""

from __future__ import annotations

import streamlit as st


def render_stock_detail(payload: dict, labels: dict) -> None:
    from niveshdristi.services.deep_dive import deep_dive
    from niveshdristi.ui.banners import render_footer
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        fmt_money,
        section_header,
        stock_card,
        why_expander,
    )
    from niveshdristi.ui.names import display_name, display_tag

    banner_strip(payload)
    symbol = payload.get("dive_symbol") or ""
    if not symbol:
        empty_state("no symbol selected",
                    "open Watchlist and press Open on a card")
        render_footer(payload, labels)
        return

    dd = deep_dive(symbol, payload.get("fund_id", ""),
                   base=payload.get("fund_base"))
    currency = labels.get("currency_code", "")
    tags = [labels.get("market_id", "")]
    tag = display_tag(symbol)
    if tag:
        tags.append(tag)

    section_header(f"Stock detail: {display_name(symbol)}",
                   f"ticker: {symbol} · " + " · ".join(tags))

    # Price chart from the stored snapshot candles
    candles = dd.get("candles")
    if candles is not None and hasattr(candles, "height") and candles.height:

        chart_frame = candles.select(
            [c for c in candles.columns if c in ("date", "close")]
        )
        st.line_chart(chart_frame, x="date", y="close", height=260)
    else:
        empty_state("no stored price data for this symbol in this fund")

    # Position info if held
    position = next(
        (p for p in payload.get("positions", [])
         if p["instrument"]["symbol"] == symbol), None)
    if position:
        avg_cost = position.get("avg_cost") or 0.0
        stock_card(
            name=display_name(symbol),
            ticker=symbol,
            tags=tags,
            metric_label="Position",
            metric_value=f"{position.get('quantity', 0)} @ "
                         f"{fmt_money(avg_cost, currency)} avg",
            caption="held in this fund (ledger-derived)",
        )
    else:
        st.caption("not held in this fund")

    # Per-model signals with their data_status
    section_header("Per-model signals",
                   "lean + conviction (uncalibrated, -1 to +1) per model")
    for m in dd.get("per_model", []):
        with st.container(key=f"signalcard_{m.get('model_id', 'model')}"):
            st.write(m.get("model_id", "?"))
            st.caption(m.get("label", ""))
            conv = m.get("conviction")
            if conv is not None:
                st.progress(min(1.0, abs(float(conv))),
                            text=f"conviction (uncalibrated): {conv:+.2f}")
            why_expander(thesis=m.get("thesis", ""))
    if not dd.get("per_model"):
        empty_state("no model signals recorded for this symbol")

    # Recent fills for this symbol (from the ledger payload)
    fills = [f for f in (payload.get("fills") or [])
             if f.get("symbol") == symbol]
    section_header("Recent orders for this symbol")
    if fills:
        for f in reversed(fills[-8:]):
            st.text(f"{f.get('side')} {f.get('quantity')} @ "
                    f"{fmt_money(f.get('price'), currency)}")
    else:
        st.caption("no fills recorded for this symbol")

    render_footer(payload, labels)
