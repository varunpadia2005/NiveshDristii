"""P19-LOOK S1: the ONE authorized CSS module.

This module injects a STATIC CSS literal via st.html. Guard rules
(tests/test_ui_style_guard.py, enforced for this file only):
- the CSS is a literal constant: no f-strings, no str.format, no
  concatenation, no data/symbols/names/user input in markup;
- no scripting tags, no external URLs/fonts/images (and no CSS import-at-rules; offline only);
- data-bearing text is rendered with native Streamlit widgets only.

Other ui/ files remain banned from any HTML surface (the amended
test_no_dangerous_surface_in_ui_and_services allowlists ONLY this file).
"""

from __future__ import annotations

import streamlit as st

STYLE_CSS = """
<style>
/* NiveshDristi original palette — deep space blue + teal accent.
   Dark-first: Streamlit exposes [data-theme="dark"] on the root. */
:root {
  --nd-bg: #0B1220;
  --nd-card: #111A2E;
  --nd-border: #1E2A44;
  --nd-text: #E6EDF7;
  --nd-muted: #93A1B8;
  --nd-accent: #2DD4BF;
  --nd-accent-soft: rgba(45, 212, 191, 0.12);
  --nd-pos: #34D399;
  --nd-neg: #FB7185;
  --nd-radius: 14px;
  --nd-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
}
[data-theme="light"] {
  --nd-bg: #F6F8FB;
  --nd-card: #FFFFFF;
  --nd-border: #E3E9F2;
  --nd-text: #101828;
  --nd-muted: #5D6B82;
  --nd-accent: #0E9488;
  --nd-accent-soft: rgba(14, 148, 136, 0.10);
  --nd-pos: #047857;
  --nd-neg: #BE123C;
  --nd-shadow: 0 4px 14px rgba(16, 24, 40, 0.08);
}

/* Cards: every keyed container gets the card treatment */
.st-key-hero, .st-key-tile, [class*="st-key-stockcard"], .st-key-signalcard,
.st-key-panel, .st-key-haltpill {
  background: var(--nd-card);
  border: 1px solid var(--nd-border);
  border-radius: var(--nd-radius);
  box-shadow: var(--nd-shadow);
  padding: 18px 20px;
  transition: border-color 120ms ease, transform 120ms ease;
}
[class*="st-key-stockcard"]:hover, .st-key-tile:hover {
  border-color: var(--nd-accent);
  transform: translateY(-2px);
}

/* Big hero number */
.st-key-hero [data-testid="stMetricValue"] {
  font-size: 2.4rem;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.st-key-hero [data-testid="stMetricLabel"] p {
  color: var(--nd-muted);
  font-weight: 600;
}

/* Metric tiles: smaller, calmer */
.st-key-tile [data-testid="stMetricValue"] { font-size: 1.3rem; }

/* Positive / negative deltas: colour AND the sign carries meaning */
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaValue"]-positive {
  color: var(--nd-pos);
}
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaValue"]-negative {
  color: var(--nd-neg);
}

/* Accent chips for status pills (native widgets inside a keyed container) */
.st-key-statuspill p {
  color: var(--nd-accent);
  font-weight: 600;
}
.st-key-haltpill { border-color: var(--nd-neg); }

/* Section headers */
h3.nd-section {
  color: var(--nd-text);
  letter-spacing: 0.2px;
}

/* Compact dataframes */
[data-testid="stDataFrame"] {
  border: 1px solid var(--nd-border);
  border-radius: var(--nd-radius);
  overflow: hidden;
}

/* Main column breathing room */
[data-testid="stMainBlockContainer"] { padding-top: 1.2rem; }

/* Sidebar nav: calmer, accent on the selected item */
[data-testid="stSidebar"] .st-radio p { color: var(--nd-muted); }
[data-testid="stSidebar"] [aria-checked="true"] p {
  color: var(--nd-accent);
  font-weight: 600;
}
</style>
"""


def inject_style() -> None:
    """Render the static stylesheet once per script run."""
    st.html(STYLE_CSS)
