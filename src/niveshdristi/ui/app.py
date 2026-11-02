"""App shell + navigation (NEW, P8-S3). Paper Fund is fully built; other
pages render the standard unavailable panel until their phase."""

from __future__ import annotations

import os

import streamlit as st

PAGES = ("Overview", "Market Overview", "Deep-Dive", "Signals",
         "Backtest Lab", "Paper Fund", "Settings")


def render_app() -> None:
    st.set_page_config(page_title="NiveshDristi", layout="wide")
    st.title("NiveshDristi — educational research tool")
    page = st.sidebar.radio("Navigation", PAGES,
                            index=PAGES.index("Paper Fund"))
    from niveshdristi.services import market_labels, read_fund

    labels = market_labels()
    fund_id = st.session_state.get("fund_id") or os.environ.get(
        "NDR_FUND_ID", "paper_test")
    base = st.session_state.get("fund_base") or os.environ.get("NDR_FUND_BASE")
    try:
        payload = read_fund(fund_id, base=base)
    except Exception as exc:  # noqa: BLE001 - UI must not crash on state
        st.error(f"fund unreadable: {exc}")
        return
    if page == "Overview":
        from niveshdristi.ui.overview_page import render_fund_overview

        overview = {**payload}
        from niveshdristi.services.fund_overview import fund_overview as _fo

        try:
            overview = _fo(fund_id, base=base)
        except Exception:  # noqa: BLE001 - fall back to the base payload
            overview = {**payload, "kpis": None}
        render_fund_overview(overview, labels)
    elif page == "Market Overview":
        from niveshdristi.services.market_view import market_overview
        from niveshdristi.ui.market_page import render_market_overview

        try:
            mo = market_overview(fund_id, base=base)
        except Exception as exc:  # noqa: BLE001
            mo = {"as_of": payload["as_of"], "last_data_session": None,
                  "holiday_note": f"unavailable: {exc}", "unavailable": []}
        render_market_overview(mo, labels)
    elif page == "Signals":
        from niveshdristi.services.market_view import signals_board
        from niveshdristi.ui.market_page import render_signals_board

        try:
            rows = signals_board(fund_id, base=base)
        except Exception:  # noqa: BLE001
            rows = []
        render_signals_board(rows, payload, labels)
    elif page == "Paper Fund":
        from niveshdristi.ui.paper_page import render_paper_fund

        render_paper_fund(payload, labels)
    else:
        from niveshdristi.ui.banners import render_banners, render_footer, unavailable_panel

        render_banners(payload)
        unavailable_panel(page)
        render_footer(payload, labels)


# AppTest executes this FILE as a script; the Streamlit server does too.
if __name__ == "__main__":
    render_app()
