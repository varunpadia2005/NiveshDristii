"""Shared banner + footer components (NEW, P8-S3). One implementation so
every page shows the same non-droppable strips."""

from __future__ import annotations

import streamlit as st


def render_banners(payload: dict) -> None:
    """DataLimitations banner + RATES UNVERIFIED banner + disclaimer."""
    if payload.get("banner"):
        st.warning(payload["banner"])
    if payload.get("rates_banner"):
        st.error(payload["rates_banner"])
    st.info(payload["disclaimer"])


def render_footer(payload: dict, labels: dict, untrusted: bool = False) -> None:
    """as-of from the DATA (never the clock) + profile labels + the
    UNTRUSTED tag whenever LLM-derived text is on the page."""
    cols = st.columns([3, 2, 2])
    cols[0].caption(f"as-of: {payload.get('as_of', 'n/a')}")
    cols[1].caption(
        f"{labels.get('market_name', '')} · {labels.get('currency_code', '')}"
    )
    if untrusted:
        cols[2].caption("[UNTRUSTED display text]")


def unavailable_panel(title: str) -> None:
    """Standard panel for anything without a verified data source."""
    st.info(f"{title} — unavailable: no verified data source")
