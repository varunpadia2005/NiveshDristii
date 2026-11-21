"""Paper Fund detail + Settings pages (NEW, P8-S9)."""

from __future__ import annotations

import json

import streamlit as st


def render_paper_detail(payload: dict, labels: dict) -> None:
    from niveshdristi.services.paper_detail import (
        events_panel,
        records_page,
        session_detail,
        verify_detail,
    )
    from niveshdristi.ui.components import (
        banner_strip,
        footer_strip,
        unavailable_panel,
    )

    banner_strip(payload)
    st.subheader("Paper fund detail")

    verify = verify_detail(payload["fund_id"],
                           st.session_state.get("fund_base"))
    if verify["status"] == "verified":
        st.success("ledger verification: verified")
    else:
        st.error("ledger verification FAILED: "
                 + "; ".join(verify["problems"][:3]))

    state = st.session_state
    page = state.get("detail_page", 0)
    pag = records_page(payload["fund_id"], state.get("fund_base"), page=page)
    st.caption(f"records {pag['total']} — page {pag['page'] + 1} "
               f"of {pag['pages']}")
    c1, c2 = st.columns(2)
    if c1.button("previous page", key="prev_page") and pag["page"] > 0:
        state["detail_page"] = pag["page"] - 1
        st.rerun()
    if c2.button("next page", key="next_page") and \
            pag["page"] < pag["pages"] - 1:
        state["detail_page"] = pag["page"] + 1
        st.rerun()
    for row in pag["rows"]:
        with st.expander(f"{row['session_date']} — equity "
                         f"{row['equity_after']:.2f} — "
                         f"{len(row.get('fills', []))} fill(s)"):
            detail = session_detail(payload["fund_id"],
                                    state.get("fund_base"),
                                    row["session_date"])
            for f in detail.get("fills", []):
                from niveshdristi.ui.names import display_name

                _nm = display_name(f['symbol'])
                st.text(f"{f['side']} {f['quantity']} {_nm} "
                        f"({f['symbol']}) @ {f['price']}")
            st.text(f"costs: fees {detail['costs']['fees']:.2f}, "
                    f"commission {detail['costs']['commission']:.2f}")
            if detail.get("gate_log"):
                for g in detail["gate_log"]:
                    st.text(f"gate {g.get('gate')} {g.get('symbol', '')}: "
                            f"{g.get('outcome')} — {g.get('reason', '')}")
            else:
                st.caption("no recorded clamp entries for this decision")

    st.subheader("Events & heartbeat")
    for e in events_panel(payload["fund_id"], state.get("fund_base")):
        st.text(json.dumps(e, sort_keys=True, default=str)[:160])

    st.subheader("Decisions (sidecar)")
    decisions = payload["decisions"]
    if decisions["status"] == "verified":
        st.json(decisions["payload"])
    elif decisions["status"] == "unverified":
        st.warning("UNVERIFIED decision sidecar (hash mismatch)")
        if decisions["payload"] is not None:
            st.json(decisions["payload"])
    else:
        st.caption("decisions not recorded")

    # flag-gated halt/resume, re-tested: confirmation required
    if st.session_state.get("allow_write_actions"):
        st.divider()
        if st.checkbox("Confirm halt", key="confirm_halt_detail"):
            if st.button("halt fund", key="halt_detail_btn"):
                from datetime import date as _date

                from niveshdristi.paper.killswitch import halt

                halt(_fund_paths(payload), fund_id=payload["fund_id"],
                     reason="ui detail halt",
                     session=_date.fromisoformat(payload["as_of"]),
                     event_id=f"halt-{payload['fund_id']}")
                st.success("halted")
    unavailable_panel("parameter overrides (read-only tool)")
    footer_strip(payload, labels)


def _fund_paths(payload: dict):
    from niveshdristi.paper.fund import FundPaths

    return FundPaths(st.session_state.get("fund_base")).for_fund(
        payload["fund_id"])


def render_settings(payload: dict, labels: dict) -> None:
    from niveshdristi.services.paper_detail import settings_view
    from niveshdristi.ui.components import banner_strip, footer_strip

    banner_strip(payload)
    st.subheader("Settings (read-only)")
    s = settings_view()
    st.text(f"market: {s['market_labels']['market_name']} "
            f"({s['market_labels']['market_id']}), currency "
            f"{s['market_labels']['currency_code']}")
    st.text(f"LLM provider/model: {s['llm_provider']} / {s['llm_model']} "
            "(VERIFY: model ids unverified)")
    st.text(f"data provider: {s['data_provider']}")
    st.text(f"cost schedule verified: {s['cost_schedule_verified']} "
            "(RATES UNVERIFIED on this data)")
    for name, present in s["keys"].items():
        st.text(f"{name}: {'●●● set' if present else 'not set'}")
    st.table(s["data_sources"])
    footer_strip(payload, labels)
