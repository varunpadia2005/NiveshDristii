"""Design tokens (NEW, P8-S4) — pure data, both themes.

Light is the default. Every text/background pair is contrast-checked in
tests/test_theme.py (>= 4.5 body text, >= 3.0 large text / UI borders);
ratios are computed and REPORTED, never asserted blind. No CSS is
injected; Streamlit's own theme + widgets consume these values."""

from __future__ import annotations

LIGHT = {
    "app_background": "#F8FAFC",
    "card": "#FFFFFF",
    "border": "#64748B",   # 4.04:1 on card (WCAG 3:1 non-text)
    "text": "#0F172A",
    "muted_text": "#475569",       # small text
    "tertiary_text": "#64748B",    # large or non-essential only
    "primary": "#4F46E5",          # buttons/links/active nav only
    "on_primary": "#FFFFFF",
    "positive_text": "#047857",
    "positive_bg": "#ECFDF5",
    "negative_text": "#BE123C",
    "negative_bg": "#FFF1F2",
    "neutral_text": "#475569",
    "neutral_bg": "#F1F5F9",
    "stub_text": "#6D28D9",
    "stub_bg": "#F5F3FF",
    "caution_text": "#92400E",     # amber banner, dark text
    "caution_bg": "#FFFBEB",
    "caution_border": "#F59E0B",
}

DARK = {
    "app_background": "#0B1220",
    "card": "#111A2E",
    "border": "#64748B",   # 4.19:1 on card (WCAG 3:1 non-text)
    "text": "#E2E8F0",
    "muted_text": "#94A3B8",
    "tertiary_text": "#94A3B8",
    "primary": "#818CF8",
    "on_primary": "#0B1220",
    "positive_text": "#6EE7B7",
    "positive_bg": "#0C2A22",
    "negative_text": "#FDA4AF",
    "negative_bg": "#2A0A12",
    "neutral_text": "#CBD5E1",
    "neutral_bg": "#16213A",
    "stub_text": "#C4B5FD",
    "stub_bg": "#1E1B3A",
    "caution_text": "#FDE68A",
    "caution_bg": "#2C2410",
    "caution_border": "#D97706",
}

THEMES = {"light": LIGHT, "dark": DARK}
