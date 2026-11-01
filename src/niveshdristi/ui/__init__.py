"""ui/ — Streamlit thin client (NEW, P8-S3).

NEUTRAL ZONE: imports ONLY services/, streamlit, plotly, stdlib. No market
literals, no currency symbols, no execution/broker/order/llm imports. The
app is READ-ONLY by default; halt/resume only through the same functions
the CLI uses, behind an explicit confirmation and a config flag that is
OFF by default. NOT run during tests or the gate (AppTest only, no server).
"""

from niveshdristi.ui.app import render_app

__all__ = ["render_app"]
