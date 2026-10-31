"""OPT-IN live LLM smoke probe (NEW, Phase 7 P7-S5) — DO NOT RUN in tests,
the gate, or CI. Standard library only (urllib); reads the provider key from
the process environment at call time; prints ONLY a redacted summary.

Usage (manual, at your own risk — provider terms and model ids UNVERIFIED):
    set NDR_LLM_KEY=...            (Windows; or export NDR_LLM_KEY=...)
    python tools/probe_llm.py --base-url https://openrouter.ai/api/v1 \
        --model some/model --prompt "Say OK"

The key is sent ONLY in the Authorization header of this single request and
is never printed, logged, cached, or written anywhere. The response is
printed as a REDACTED summary (secret patterns scrubbed by
niveshdristi.llm.safety.redact).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))

from niveshdristi.llm.safety import redact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live LLM smoke probe")
    parser.add_argument("--base-url", required=True, help="Provider API base URL")
    parser.add_argument("--model", required=True, help="Model id (UNVERIFIED)")
    parser.add_argument("--prompt", default="Say OK")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    key = __import__("os").environ.get("NDR_LLM_KEY", "")
    if not key:
        print("NDR_LLM_KEY not set in the environment — nothing sent.", file=sys.stderr)
        return 2

    payload = json.dumps({
        "model": args.model,
        "messages": [
            {"role": "system", "content": "Reply with exactly: OK"},
            {"role": "user", "content": args.prompt},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # REDACTED summary only — never the key, never raw headers
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
