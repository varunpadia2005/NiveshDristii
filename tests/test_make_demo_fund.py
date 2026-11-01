"""D1c: the demo-fund generator is offline, synthetic-only, and its tamper
copies are verifiably broken copies."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestMakeDemoFund:
    def test_build_offline_into_tmp(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO, timeout=900,
        )
        assert proc.returncode == 0, proc.stderr[-400:]
        fund = tmp_path / "demo_synthetic"
        lines = fund.joinpath("ledger.jsonl").read_text(
            encoding="utf-8").splitlines()
        records = [x for x in lines if "session_date" in x]
        assert len(records) == 130
        header = json.loads(lines[0])
        assert header["note"].startswith("SYNTHETIC DEMO")
        assert list((fund / "decisions").glob("*.json"))
        # SYN-named instruments only
        text = fund.joinpath("ledger.jsonl").read_text(encoding="utf-8")
        assert "SYN090" in text
        assert "RELIANCE" not in text

    def test_tamper_copies_are_corrupted_copies(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, "tools/make_demo_fund.py", "--base", str(tmp_path),
             "--tamper-ledger", "--tamper-sidecar"],
            capture_output=True, text=True, cwd=REPO, timeout=900,
        )
        assert proc.returncode == 0, proc.stderr[-400:]
        t = tmp_path / "demo_synthetic_tampered_ledger"
        assert t.exists()
        sys.path.insert(0, str(REPO / "src"))
        from niveshdristi.paper.ledger import PaperLedger

        problems = PaperLedger(t / "ledger.jsonl").verify()
        assert problems, "tampered ledger must fail verification"
