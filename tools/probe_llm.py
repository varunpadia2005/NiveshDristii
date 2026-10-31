"""OPT-IN live LLM smoke probe (NEW, Phase 7 P7-S5; R8 1g hardening) — DO
NOT RUN in tests, the gate, or CI. Standard library only (urllib).

DRY RUN BY DEFAULT: without --yes-make-network-call the tool prints the
REDACTED request body and whether a key is present (never its value) and
exits — no network is touched. The fixed prompt is harmless ("Reply with
exactly: OK"); no repo, fund or portfolio data is ever sent. max_tokens and
the timeout are hard-capped below.

Usage (manual, at your own risk — provider terms and model ids UNVERIFIED):
    set NDR_LLM_KEY=...            (Windows; or export NDR_LLM_KEY=...)
    python tools/probe_llm.py --base-url https://openrouter.ai/api/v1 --model some/model
    python tools/probe_llm.py --base-url ... --model ... --yes-make-network-call

The key is sent ONLY in the Authorization header of this single request and
is never printed, logged, cached, or written anywhere. The response is
printed as a REDACTED summary (secret patterns scrubbed by
niveshdristi.llm.safety.redact).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from niveshdristi.llm.safety import redact  # noqa: E402

FIXED_PROMPT = "Reply with exactly: OK"
MAX_TOKENS_CAP = 64
TIMEOUT_CAP_SECONDS = 30.0


def build_payload(model: str) -> str:
    """The fixed harmless request body (no repo/fund/portfolio data)."""
    return json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": FIXED_PROMPT},
            {"role": "user", "content": FIXED_PROMPT},
        ],
        "max_tokens": MAX_TOKENS_CAP,
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in live LLM smoke probe")
    parser.add_argument("--base-url", required=True, help="Provider API base URL")
    parser.add_argument("--model", required=True, help="Model id (UNVERIFIED)")
    parser.add_argument(
        "--yes-make-network-call", action="store_true",
        help="REQUIRED to actually send; without it the tool dry-runs",
    )
    parser.add_argument("--timeout", type=float, default=TIMEOUT_CAP_SECONDS)
    args = parser.parse_args(argv)

    key_present = bool(os.environ.get("NDR_LLM_KEY"))
    payload = build_payload(args.model)
    print("=== DRY RUN (no network) ===" if not args.yes_make_network_call
          else "=== LIVE CALL AUTHORIZED BY FLAG ===")
    print(json.dumps({
        "url": args.base_url.rstrip("/") + "/chat/completions",
        "payload_redacted": redact(payload, {}),
        "max_tokens_cap": MAX_TOKENS_CAP,
        "timeout_cap_seconds": TIMEOUT_CAP_SECONDS,
        "key_present": key_present,   # presence only — NEVER the value
    }, indent=2))
    if not args.yes_make_network_call:
        print("Dry run only. Pass --yes-make-network-call to send.", file=sys.stderr)
        return 0
    if not key_present:
        print("NDR_LLM_KEY not set in the environment — nothing sent.", file=sys.stderr)
        return 2

    timeout = min(args.timeout, TIMEOUT_CAP_SECONDS)
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=payload.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['NDR_LLM_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {redact(exc.reason, {})}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - operator-facing summary only
        print(f"error: {redact(str(exc), {})}", file=sys.stderr)
        return 1

    text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(json.dumps({
        "model": body.get("model", args.model),
        "reply_redacted": redact(text, {}),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
