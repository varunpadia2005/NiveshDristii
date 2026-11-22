"""P20-WEB S1: read-only JSON API for the Next.js frontend.

Standard library only (R4): http.server, GET only, loopback only.
- CORS: Access-Control-Allow-Origin allows ONLY the localhost:3000
  origins of the web app; every other Origin gets no CORS header.
- Fund ids are validated against the fund base directory (no traversal).
- Responses are JSON built by the existing services view-models — the
  web layer adds no numbers of its own.
- Errors: {"error": ..., "hint": ...} with proper status codes.

Entry point:
    python -m niveshdristi.webapi --fund-base <dir> [--port 8000]
(--port 0.0.0.0 binding is refused; loopback only.)
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class ApiError(Exception):
    def __init__(self, status: int, error: str, hint: str) -> None:
        self.status = status
        self.error = error
        self.hint = hint


def list_funds(base: str | Path) -> list[str]:
    """Fund ids = directories under the base carrying a ledger.jsonl."""
    root = Path(base)
    if not root.is_dir():
        raise ApiError(400, f"fund base not found: {root}",
                       "pass --fund-base pointing at the demo funds dir")
    out = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "ledger.jsonl").is_file():
            out.append(child.name)
    return out


def resolve_fund(base: str | Path, fund: str | None) -> Path:
    """Validate the fund id against the base dir (no path traversal)."""
    if not fund or not _SAFE_ID.match(fund):
        raise ApiError(400, f"invalid fund id: {fund!r}",
                       "fund ids are plain directory names")
    if fund in (".", ".."):
        raise ApiError(400, f"invalid fund id: {fund!r}",
                       "fund ids are plain directory names")
    path = Path(base) / fund
    # Containment: the resolved path must stay INSIDE the base dir even
    # if the name slips past the regex (defence in depth for traversal).
    if not path.resolve().is_relative_to(Path(base).resolve()):
        raise ApiError(400, f"fund id escapes the fund base: {fund!r}",
                       "fund ids are plain directory names")
    if not path.is_dir():
        raise ApiError(404, f"unknown fund: {fund!r}",
                       "GET /api/funds lists the available funds")
    return path


def call_service(name: str, base: str, fund: str | None,
                 symbol: str | None) -> dict:
    """Dispatch to the read-only services view-models. Import inside so
    the module import stays cheap and testable."""
    if name == "funds":
        return {"funds": list_funds(base)}
    if name == "settings":
        from niveshdristi.services.paper_detail import settings_view

        return settings_view()
    path = resolve_fund(base, fund)
    assert fund is not None  # resolve_fund guarantees a valid id
    _ = path  # fund id already validated; services re-validate internally
    if name == "overview":
        from niveshdristi.services.fund_overview import fund_overview

        return fund_overview(fund, base=base)
    if name == "nav":
        from niveshdristi.services.fund_overview import nav_series

        return {"series": nav_series(fund, base=base)}
    if name == "watchlist":
        from niveshdristi.services.market_view import watchlist

        return watchlist(fund, base=base)
    if name == "signals":
        from niveshdristi.services.market_view import signals_board

        return {"rows": signals_board(fund, base=base)}
    if name == "market":
        from niveshdristi.services.market_view import market_overview

        return market_overview(fund, base=base)
    if name == "holdings":
        from niveshdristi.services.fund_overview import holdings_view

        return holdings_view(fund, base=base)
    if name == "orders":
        from niveshdristi.services.paper_detail import orders_view

        return orders_view(fund, base=base)
    if name == "paper":
        from niveshdristi.services.fund import read_fund

        return read_fund(fund, base=base)
    if name == "deepdive":
        if not symbol or not _SAFE_ID.match(symbol):
            raise ApiError(400, f"invalid symbol: {symbol!r}",
                           "symbols are plain tickers")
        from niveshdristi.services.deep_dive import deep_dive

        return deep_dive(symbol, fund, base=base)
    if name == "backtest":
        from niveshdristi.services.backtest_lab import (
            content_key,
            run_backtest_service,
        )

        key = content_key(fund, base)
        return run_backtest_service(fund, base, _key=key)
    raise ApiError(404, f"unknown endpoint: {name!r}",
                   "see the endpoint list in web/README.md")


class Handler(BaseHTTPRequestHandler):
    fund_base: str = ""

    def do_GET(self) -> None:  # noqa: N802 - http.server API name
        origin = self.headers.get("Origin", "")
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        fund = qs.get("fund", [None])[0]
        symbol = qs.get("symbol", [None])[0]
        name = parsed.path.removeprefix("/api/").strip("/") or "funds"
        try:
            payload = call_service(name, self.fund_base, fund, symbol)
            body = json.dumps(payload, default=str).encode("utf-8")
            self._respond(200, body, origin)
        except ApiError as exc:
            self._respond(exc.status, json.dumps(
                {"error": exc.error, "hint": exc.hint}).encode("utf-8"),
                origin)
        except Exception as exc:  # noqa: BLE001 - typed JSON error out
            self._respond(500, json.dumps(
                {"error": f"{type(exc).__name__}: {exc}",
                 "hint": "see the server log"}).encode("utf-8"), origin)

    def _respond(self, status: int, body: bytes, origin: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if origin in _ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        self._reject_method()

    def do_PUT(self) -> None:  # noqa: N802
        self._reject_method()

    def do_DELETE(self) -> None:  # noqa: N802
        self._reject_method()

    def _reject_method(self) -> None:
        self._respond(405, json.dumps(
            {"error": "method not allowed — this API is read-only (GET)",
             "hint": "use GET; the web layer never mutates funds"}
        ).encode("utf-8"), self.headers.get("Origin", ""))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        print(f"[webapi] {self.address_string()} {format % args}")


def build_server(fund_base: str, port: int) -> ThreadingHTTPServer:
    """Bind 127.0.0.1 ONLY; refuses any other host."""
    handler = type("BoundHandler", (Handler,), {"fund_base": fund_base})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NiveshDristi read-only JSON API (loopback only)")
    parser.add_argument("--fund-base", required=True)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.port < 0:
        raise SystemExit("--port must be >= 0")
    server = build_server(args.fund_base, args.port)
    host, bound_port = server.server_address[:2]
    if host != "127.0.0.1":
        raise SystemExit("refusing to bind anything but 127.0.0.1")
    print(f"[webapi] serving GET-only JSON API on http://{host}:{bound_port} "
          f"(fund base: {args.fund_base})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[webapi] stopping")


if __name__ == "__main__":
    main()
