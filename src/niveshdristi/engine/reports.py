"""Report generation (NEW, Phase 5): deterministic JSON + self-contained
Plotly HTML. Reports are written ONLY to a caller-supplied path (tests use
tmp_path); never into the repo.

Mandatory content (constructor-enforced where possible, tested everywhere):
- the DataLimitations banner, the RATES UNVERIFIED banner (when
  rates_verified is False), the calendar source, and an "as of" date taken
  from the LAST SESSION DATE of the data (never the system clock).

plotly.js is embedded INLINE in the HTML (no CDN, no network at view time).
JSON is deterministic: sorted keys, fixed float formatting, byte-identical
across runs.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from niveshdristi.core.limitations import DataLimitations
from niveshdristi.engine.backtest import BacktestResult

RATES_BANNER = "RATES UNVERIFIED"
JAVASCRIPT_DISABLED_NOTE = "JavaScript is disabled or unavailable in this browser."


def _fmt(value: float) -> str:
    """Fixed float formatting for deterministic JSON (6 decimal places)."""
    return f"{value:.6f}"


def build_report_json(
    result: BacktestResult,
    *,
    limitations: DataLimitations,
    rates_verified: bool,
    calendar_source: str,
    as_of: date,
    label: str = "backtest",
) -> str:
    """Deterministic JSON text (sorted keys, fixed floats)."""
    payload = {
        "as_of": as_of.isoformat(),
        "banner": limitations.banner or "",
        "calendar_source": calendar_source,
        "drag_bps": round(result.drag_bps, 6),
        "fees_total": round(result.fees_total, 6),
        "gross_equity_final": round(result.gross_equity_curve[-1][1], 6),
        "label": label,
        "limitations": sorted(limitations.CODES),
        "net_equity_curve": [
            [day.isoformat(), _fmt(v)] for day, v in result.net_equity_curve
        ],
        "rates_verified": rates_verified,
        "rates_banner": "" if rates_verified else RATES_BANNER,
        "slippage_total": round(result.slippage_total, 6),
        "tax_accrued": round(result.tax_accrued, 6),
        "trade_count": result.trade_count,
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def build_report_html(
    result: BacktestResult,
    *,
    limitations: DataLimitations,
    rates_verified: bool,
    calendar_source: str,
    as_of: date,
    label: str = "backtest",
    currency_label: str = "units",
) -> str:
    """Self-contained Plotly HTML (plotly.js inline; no CDN, no network)."""
    import plotly.graph_objects as go  # main dependency, already declared

    days_net = [d.isoformat() for d, _ in result.net_equity_curve]
    net = [v for _, v in result.net_equity_curve]
    gross = [v for _, v in result.gross_equity_curve]
    peak = net[0] if net else 0.0
    dd = []
    for value in net:
        peak = max(peak, value)
        dd.append(value - peak)

    rates_line = "" if rates_verified else RATES_BANNER
    lim_line = limitations.banner or ""
    title = (
        f"{label} | as of {as_of.isoformat()} | calendar: {calendar_source} "
        f"| {lim_line} | {rates_line}"
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=days_net, y=gross, name="gross (before all frictions)", mode="lines")
    )
    fig.add_trace(
        go.Scatter(x=days_net, y=net, name="net (after fees + slippage)", mode="lines")
    )
    fig.add_trace(
        go.Scatter(x=days_net, y=dd, name="net drawdown", mode="lines", visible="legendonly")
    )
    fig.update_layout(
        title={"text": title},
        xaxis_title="session",
        yaxis_title=f"equity ({currency_label})",
        dragmode="pan",
    )
    inner = fig.to_html(
        include_plotlyjs=True,  # inline plotly.js: no CDN, no network
        full_html=True,
        config={"displaylogo": False},
    )
    fallback = (
        f"<p>{JAVASCRIPT_DISABLED_NOTE}</p>"
        f"<pre>net_final={_fmt(net[-1] if net else 0.0)}; "
        f"drag_bps={_fmt(result.drag_bps)}</pre>"
    )
    html_text: str = inner.replace(
        "<body>", f"<body><h3>{title}</h3>{fallback}<hr/>", 1
    )
    return html_text


def write_report_files(
    result: BacktestResult,
    *,
    out_dir: str | Path,
    limitations: DataLimitations,
    rates_verified: bool,
    calendar_source: str,
    as_of: date,
    label: str = "backtest",
) -> tuple[Path, Path]:
    """Write report files under the caller-supplied directory (never the repo)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_text = build_report_json(
        result, limitations=limitations, rates_verified=rates_verified,
        calendar_source=calendar_source, as_of=as_of, label=label,
    )
    html_text = build_report_html(
        result, limitations=limitations, rates_verified=rates_verified,
        calendar_source=calendar_source, as_of=as_of, label=label,
    )
    json_path = out / f"{label}_report.json"
    json_path.write_text(json_text, encoding="utf-8")
    html_path = out / f"{label}_report.html"
    html_path.write_text(html_text, encoding="utf-8")
    return json_path, html_path
