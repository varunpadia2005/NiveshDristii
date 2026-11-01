"""Paper Fund page (NEW, P8-S3) — the first fully built page. Read-only
except halt/resume, which are gated by an explicit config flag (OFF by
default) and a per-action confirmation, and executed through the SAME
functions the CLI uses."""

from __future__ import annotations

import streamlit as st


def render_paper_fund(payload: dict, labels: dict) -> None:
    from niveshdristi.ui.banners import render_banners, render_footer

    render_banners(payload)
    st.subheader(f"Paper fund: {payload['fund_id']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("records", payload["records"])
    c2.metric("cash", payload["cash"] if payload["cash"] is not None else "—")
    verify = payload["verify"]
    (c3 if verify == "verified" else c3).metric(
        "ledger verify", verify if verify == "verified" else "FAILED (loud)"
    )
    if payload.get("halted"):
        st.error(f"HALTED: {payload.get('halt_reason')}")
    st.table(payload["positions"] if payload["positions"] else [])

    st.subheader("Decisions & theses")
    decisions = payload["decisions"]
    if decisions["status"] == "verified":
        st.json(decisions["payload"])
    elif decisions["status"] == "unverified":
        st.warning("UNVERIFIED decision sidecar (content hash mismatch) — "
                   "display only, never trusted")
        if decisions["payload"] is not None:
            st.json(decisions["payload"])
    else:
        st.caption("decisions not recorded")

    if st.session_state.get("allow_write_actions"):
        st.divider()
        st.caption("Write actions are ENABLED by config flag (off by default)")
        if st.checkbox("Confirm halt", key="confirm_halt"):
            if st.button("halt fund", key="halt_fund_btn"):
                from datetime import date as _date

                from niveshdristi.paper.killswitch import halt

                halt_payload = halt(
                    st.session_state["fund_paths"], fund_id=payload["fund_id"],
                    reason="ui halt",
                    session=_date.fromisoformat(payload["as_of"]),
                    event_id=f"halt-{payload['fund_id']}",
                )
                st.success(f"halted ({halt_payload.get('session')})")
    render_footer(payload, labels)
