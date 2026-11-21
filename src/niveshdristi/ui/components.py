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


# ---------------------------------------------------------------------------
# P18-UI-S1: retail-style reusable components. Streamlit widgets only — the
# guard tests ban st.markdown / unsafe_allow_html / raw HTML, and ban
# hard-coded currency symbols; formatting takes the currency CODE from the
# market labels (MarketRules), never a symbol literal.
# ---------------------------------------------------------------------------


def fmt_money(value: float | None, currency_code: str = "") -> str:
    """Thousands separators + 2 dp; the currency CODE travels with the
    number (no symbol literal — the guard test bans them). None -> em dash."""
    if value is None:
        return "—"
    from niveshdristi.services.format import format_money_code

    return (format_money_code(value, currency_code)
            + (f" {currency_code}" if currency_code else ""))


def fmt_pct(value: float | None) -> str:
    """Signed percent with 2 dp; None -> em dash."""
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def change_chip(delta_value: float | None, currency_code: str = "") -> None:
    """Price/change chip: st.metric's delta carries the arrow AND sign, and
    the caption carries the WORD (up/down/flat) so colour is never the only
    channel. Neutral (None/0) renders as an explicit flat state."""
    if delta_value is None:
        st.metric(label="Change", value="—")
        st.caption("no change data")
        return
    word = "up" if delta_value > 0 else "down" if delta_value < 0 else "flat"
    st.metric(label="Change", value=fmt_money(delta_value, currency_code),
              delta=delta_value,
              delta_color="normal" if delta_value else "off")
    st.caption(f"{word} vs previous close")


def metric_tile(*, label: str, value: str, caption: str = "") -> None:
    """Metric tile (alias of kpi_card with keyword-only args) - the
    information-dense tile used across the redesigned pages."""
    kpi_card(label=label, value=value, caption=caption)


def stock_card(*, name: str, ticker: str, tags: list[str],
               metric_label: str = "", metric_value: str = "",
               caption: str = "") -> None:
    """One stock card: display name, ticker chip, honest tags (exchange,
    'synthetic demo data'), optional metric and caption."""
    with st.container(border=True):
        head = st.columns([3, 2])
        head[0].write(name)
        head[1].caption(ticker)
        if tags:
            st.caption(" · ".join(tags))
        if metric_label:
            st.metric(label=metric_label, value=metric_value or "—")
        if caption:
            st.caption(caption)


def section_header(text: str, caption: str = "") -> None:
    """Section header + optional caption (replaces bare st.subheader calls
    so every section reads the same)."""
    st.subheader(text)
    if caption:
        st.caption(caption)


def empty_state(text: str, next_action: str = "") -> None:
    """Empty state WITH a next action (the bare caption version became this
    during P18-UI-S1 — callers without a next action keep working)."""
    st.info(text)
    if next_action:
        st.caption(f"Next: {next_action}")
