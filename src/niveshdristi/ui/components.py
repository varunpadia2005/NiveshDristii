"""Shared UI components (NEW, P8-S4) — pure Streamlit widgets, NO CSS, and no
raw-HTML surface of any kind. Light/calm/information-dense: verdict first, evidence
behind expanders."""

from __future__ import annotations

import streamlit as st


def kpi_card(label: str, value: str, caption: str = "") -> None:
    """One information-dense KPI (st.metric inside a bordered column)."""
    with st.container(border=True):
        st.metric(label=label, value=value)
        if caption:
            st.caption(caption)


def signal_pill(lean: str, qualifier: str = "") -> None:
    """Icon + word pill (the lean string already carries its icon); never
    colour alone — the word carries the meaning."""
    text = lean + (f" ({qualifier})" if qualifier else "")
    st.caption(text)


def banner_strip(payload: dict) -> None:
    """NON-DROPPABLE: DataLimitations list, RATES UNVERIFIED, disclaimer —
    a page cannot render without these (S3 component, kept here)."""
    from niveshdristi.ui.banners import render_banners

    render_banners(payload)


def footer_strip(payload: dict, labels: dict, untrusted: bool = False) -> None:
    from niveshdristi.ui.banners import render_footer

    render_footer(payload, labels, untrusted=untrusted)


def loading_placeholder(text: str = "Loading…") -> None:
    st.spinner(text)


def empty_state(text: str) -> None:
    st.caption(text)


def error_state(text: str) -> None:
    st.error(text)


def unavailable_panel(title: str) -> None:
    """Panels with no verified data source — NEVER fixtures or estimates."""
    st.info(f"{title} — unavailable: no verified data source")


def why_expander(*, thesis: str, evidence: dict | None = None) -> None:
    """Progressive disclosure: the "Why?" expander on every signal. Text is
    rendered INERT (st.text)."""
    with st.expander("Why?"):
        st.text(thesis)
        if evidence:
            st.text(", ".join(f"{k}={v}" for k, v in sorted(evidence.items())))


def legend() -> None:
    """Direction legend: up = green, down = red (local convention), shown as
    icon + word so colour is never the only channel."""
    st.caption("Legend: ▲ Positive lean (up, green) · ▼ Negative lean "
               "(down, red) · — Neutral")
