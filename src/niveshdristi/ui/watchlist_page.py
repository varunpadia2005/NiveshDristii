"""Watchlist / Explore page (P18-UI-S3b).

Search box filters by resolved display name or ticker; every fund
universe symbol renders as a stock card with last close and change
(from the fund's stored snapshots — never invented); selecting a card
stores the symbol for the Stock Detail page.
"""

from __future__ import annotations

import streamlit as st


def render_watchlist(payload: dict, labels: dict) -> None:
    from niveshdristi.services.market_view import watchlist
    from niveshdristi.ui.components import (
        banner_strip,
        empty_state,
        fmt_money,
        footer_strip,
        section_header,
        stock_card,
    )
    from niveshdristi.ui.names import display_name, display_tag

    banner_strip(payload)
    section_header("Watchlist", "every symbol the fund tracks — last close "
                   "and change only where the fund has stored snapshot data")
    data = watchlist(payload.get("fund_id", ""),
                     base=payload.get("fund_base"))
    rows = data.get("rows", [])

    query = st.text_input("Search", placeholder="name or ticker",
                          help="filters by display name or ticker")
    held_symbols = {p["instrument"]["symbol"]
                    for p in payload.get("positions", [])}

    def _direction(r: dict) -> str:
        if r["change"] is None:
            return "flat"
        return "gainers" if r["change"] > 0 else "losers"

    pill = st.pills("Filter", ["All", "Held", "Gainers", "Losers"],
                    selection_mode="single", default="All")
    q = (query or "").strip().upper()
    matched = [r for r in rows
               if not q or q in r["symbol"].upper()
               or q in display_name(r["symbol"]).upper()]
    if pill == "Held":
        matched = [r for r in matched if r["symbol"] in held_symbols]
    elif pill == "Gainers":
        matched = [r for r in matched if _direction(r) == "gainers"]
    elif pill == "Losers":
        matched = [r for r in matched if _direction(r) == "losers"]

    if not rows:
        empty_state("this fund tracks no symbols",
                    "generate a demo fund with tools/make_demo_fund.py")
        footer_strip(payload, labels)
        return
    if not matched:
        empty_state(f"no symbol matches “{query}”",
                    "clear the search box to see every tracked symbol")

    currency = labels.get("currency_code", "")
    cols = st.columns(min(3, max(1, len(matched))))
    for i, row in enumerate(matched):
        with cols[i % len(cols)]:
            tags = [labels.get("market_id", "")]
            tag = display_tag(row["symbol"])
            if tag:
                tags.append(tag)
            if row["has_data"]:
                with st.container(key=f"stockcard_{row['symbol']}"):
                    st.write(f"{display_name(row['symbol'])}")
                    st.caption(f"{row['symbol']} · " + " · ".join(tags))
                    st.metric("Last close",
                              fmt_money(row["last_close"], currency),
                              delta=row["change"],
                              delta_color="normal" if row["change"] else "off")
                    direction = _direction(row)
                    st.caption(f"{direction} vs previous close")
                    closes = row.get("closes") or []
                    if len(closes) >= 2:
                        import pandas as pd

                        spark = pd.DataFrame(
                            {"close": closes},
                            index=list(range(len(closes))),
                        )
                        st.line_chart(spark, height=60)
                    if st.button("Open", key=f"open_{row['symbol']}"):
                        st.session_state["dive_symbol"] = row["symbol"]
            else:
                stock_card(
                    name=display_name(row["symbol"]),
                    ticker=row["symbol"],
                    tags=tags,
                    caption="no stored data for this fund yet",
                )
    footer_strip(payload, labels)
