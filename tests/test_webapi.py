"""P20-WEB S1: read-only JSON API tests.

Real HTTP against build_server() on an ephemeral loopback port, over
freshly generated demo funds (repo's own offline generator). Every
number equality-asserted against the ledger/services; security pins:
path traversal, unknown fund, method rejection, CORS origin rules.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def demo_base(tmp_path_factory):
    base = tmp_path_factory.mktemp("webapi_demo")
    for market, fund in (("IN_NSE", "p20_in"), ("US_NYSE", "p20_us")):
        r = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(base),
             "--market", market, "--fund-id", fund],
            capture_output=True, text=True, cwd=str(REPO), timeout=600,
        )
        assert r.returncode == 0, r.stderr[-300:]
    return base


@pytest.fixture(scope="module")
def api(demo_base):
    from niveshdristi.webapi.server import build_server

    server = build_server(str(demo_base), 0)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}", demo_base
    server.shutdown()


def _get(url: str, origin: str | None = None) -> tuple[int, dict, dict]:
    req = urllib.request.Request(url)
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), \
                dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8")), \
            dict(exc.headers)


class TestApiFundEndpoints:
    def test_funds_lists_both_demo_funds(self, api):
        base_url, base = api
        status, body, _ = _get(f"{base_url}/api/funds")
        assert status == 200
        assert set(body["funds"]) >= {"p20_in", "p20_us"}

    def test_overview_equals_ledger(self, api):
        base_url, base = api
        status, body, _ = _get(f"{base_url}/api/overview?fund=p20_in")
        assert status == 200
        ledger = (base / "p20_in" / "ledger.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        last = json.loads(ledger[-1])
        assert body["cash"] == last["cash_after"]
        assert body["as_of"] == last["session_date"]

    def test_nav_series_length_equals_records(self, api):
        base_url, base = api
        _, nav, _ = _get(f"{base_url}/api/nav?fund=p20_in")
        records = [json.loads(line) for line in (base / "p20_in" / "ledger.jsonl")
                   .read_text(encoding="utf-8").strip().splitlines()]
        records = [r for r in records if "session_date" in r]
        assert len(nav["series"]) == len(records)
        assert nav["series"][0]["equity"] == records[0]["equity_after"]

    def test_watchlist_and_holdings_non_vacuity(self, api):
        base_url, _ = api
        _, wl, _ = _get(f"{base_url}/api/watchlist?fund=p20_in")
        assert len(wl["rows"]) >= 2
        _, us_wl, _ = _get(f"{base_url}/api/watchlist?fund=p20_us")
        assert len(us_wl["rows"]) >= 2
        _, h, _ = _get(f"{base_url}/api/holdings?fund=p20_in")
        assert h["total_value"] is not None
        assert h["total_value"] > 0

    def test_orders_and_paper_and_settings(self, api):
        base_url, _ = api
        _, o, _ = _get(f"{base_url}/api/orders?fund=p20_in")
        assert len(o["fills"]) > 0
        _, p, _ = _get(f"{base_url}/api/paper?fund=p20_in")
        assert p["fund_id"] == "p20_in"
        _, s, _ = _get(f"{base_url}/api/settings")
        assert "market_labels" in s


class TestApiSecurity:
    def test_unknown_fund_404_with_hint(self, api):
        base_url, _ = api
        status, body, _ = _get(f"{base_url}/api/overview?fund=nope")
        assert status == 404
        assert "error" in body
        assert "hint" in body

    def test_sibling_fund_outside_base_rejected(self, api):
        """Defence-in-depth: a VALID fund directory placed NEXT TO the
        base (reachable only via ../) must be refused — the mutation
        that dropped the regex check used to escape this via 404 luck."""
        base_url, base = api
        sibling = base.parent / "evil_fund"
        sibling.mkdir(exist_ok=True)
        (sibling / "ledger.jsonl").write_text("{}", encoding="utf-8")
        status, body, _ = _get(
            f"{base_url}/api/overview?fund=../evil_fund")
        assert status in (400, 404)
        assert "error" in body
        assert "hint" in body

    @pytest.mark.parametrize("evil", ["../p20_in", "..%2Fp20_in",
                                      "p20_in/../../other", ".", ".."])
    def test_path_traversal_rejected(self, api, evil):
        base_url, _ = api
        status, body, _ = _get(f"{base_url}/api/overview?fund={evil}")
        assert status in (400, 404), (evil, status, body)
        assert "error" in body
        assert "hint" in body

    def test_post_and_delete_rejected_405(self, api):
        base_url, _ = api
        for method in ("POST", "DELETE"):
            req = urllib.request.Request(
                f"{base_url}/api/overview?fund=p20_in", method=method)
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(req, timeout=30)
            assert excinfo.value.code == 405
            body = json.loads(excinfo.value.read().decode("utf-8"))
            assert body["error"].startswith("method not allowed")

    def test_cors_origin_rules(self, api):
        base_url, _ = api
        _, _, allowed_headers = _get(
            f"{base_url}/api/funds", origin="http://localhost:3000")
        assert allowed_headers.get("Access-Control-Allow-Origin") == \
            "http://localhost:3000"
        _, _, allowed2 = _get(
            f"{base_url}/api/funds", origin="http://127.0.0.1:3000")
        assert allowed2.get("Access-Control-Allow-Origin") == \
            "http://127.0.0.1:3000"
        _, _, foreign = _get(
            f"{base_url}/api/funds", origin="http://evil.example")
        assert "Access-Control-Allow-Origin" not in foreign
        _, _, none_origin = _get(f"{base_url}/api/funds")
        assert "Access-Control-Allow-Origin" not in none_origin

    def test_deepdive_endpoint(self, api):
        base_url, _ = api
        status, body, _ = _get(
            f"{base_url}/api/deepdive?fund=p20_in&symbol=SYN090")
        assert status == 200
        assert body["symbol"] == "SYN090"
        status, body, _ = _get(
            f"{base_url}/api/deepdive?fund=p20_in&symbol=../x")
        assert status == 400
