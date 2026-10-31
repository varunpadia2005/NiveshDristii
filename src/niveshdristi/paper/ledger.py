"""Append-only paper ledger (NEW, Phase 6).

Format (amendment C): UTF-8 text, "\n" line endings ONLY (opened in binary
mode so no CRLF translation can occur), sorted JSON keys, no spaces.
  Line 1: fund header (fund id, created session date, configuration digest,
          MarketRules digest, DataLimitations codes, rates_verified flag,
          library versions, ledger format version).
  Line 2+: one SessionRecord dump per line (money canonicalized to integer
          paise by SessionRecord._canonical at hash time).

The ledger is the single source of truth; the PaperBroker state file is a
cache (amendment C2). Appends are flush + os.fsync (the commit point).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from niveshdristi.core.errors import LedgerError
from niveshdristi.core.limitations import DataLimitations
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.core.session import SessionRecord

LEDGER_FORMAT_VERSION = 1


def _dump(obj) -> str:
    """Canonical JSON line: sorted keys, no spaces, no trailing newline."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def build_header(
    *,
    fund_id: str,
    created: date,
    config_digest: str,
    rules: MarketRules,
    limitations: DataLimitations,
    rates_verified: bool,
) -> dict:
    """Fund header (ledger line 1) per amendment C."""
    import polars

    return {
        "type": "fund_header",
        "ledger_format_version": LEDGER_FORMAT_VERSION,
        "fund_id": fund_id,
        "created": created.isoformat(),
        "config_digest": config_digest,
        # mode="json" handles frozensets (list) and dates — JSON-safe round trip
        "market_rules_digest": _dump(rules.model_dump(mode="json")),
        "limitation_codes": sorted(limitations.CODES),
        "rates_verified": rates_verified,
        "library_versions": {
            "python": sys.version.split()[0],
            "polars": polars.__version__,
            "numpy": __import__("numpy").__version__,
        },
    }


class PaperLedger:
    """Append-only JSONL ledger with hash-chain verification."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def create(self, header: dict) -> None:
        """Create a NEW ledger with the fund header (fails if it exists)."""
        if self.path.exists():
            raise LedgerError(f"ledger already exists: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "ab") as handle:  # binary: no CRLF translation
            handle.write((_dump(header) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())

    def append(self, record: SessionRecord, previous_hash: str) -> str:
        """Append one record with its chain link; fsync is the commit point.

        Returns the linked hash stored on the line.
        """
        linked = record.model_copy(update={"previous_hash": previous_hash})
        line = _dump({**linked.model_dump(), "hash": linked.compute_hash()})
        with open(self.path, "ab") as handle:
            handle.write((line + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        return linked.compute_hash()

    def lines(self) -> list[dict]:
        """Parse all lines; LedgerError on a partial/corrupt trailing line."""
        if not self.path.exists():
            raise LedgerError(f"ledger missing: {self.path}")
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise LedgerError(
                f"partial trailing line in {self.path} (crash mid-write?): "
                "refusing to read; repair is a manual step"
            )
        out = []
        for number, raw_line in enumerate(raw.split(b"\n"), start=1):
            if not raw_line:
                continue
            try:
                out.append(json.loads(raw_line.decode("utf-8")))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise LedgerError(f"corrupt ledger line {number}: {exc}") from exc
        return out

    def header(self) -> dict:
        lines = self.lines()
        if not lines or lines[0].get("type") != "fund_header":
            raise LedgerError("ledger line 1 is not a fund header")
        return lines[0]

    def records(self) -> list[dict]:
        return [line for line in self.lines() if line.get("type") != "fund_header"]

    def last_session_date(self) -> date | None:
        records = self.records()
        if not records:
            return None
        return date.fromisoformat(records[-1]["session_date"])

    def last_hash(self) -> str:
        records = self.records()
        return records[-1]["hash"] if records else "0" * 64

    def verify(self) -> list[str]:
        """Recompute every hash and the previous-hash links.

        Returns a list of problems (empty = verified); each names the line.
        """
        problems: list[str] = []
        lines = self.lines()
        prev = "0" * 64
        for number, line in enumerate(lines[1:], start=2):  # skip header
            stored = {k: v for k, v in line.items() if k != "hash"}
            record = SessionRecord.model_validate(stored)
            expected_prev = line["previous_hash"]
            if expected_prev != prev:
                problems.append(
                    f"line {number}: previous_hash {expected_prev!r} != "
                    f"expected {prev!r}"
                )
            if record.compute_hash() != line["hash"]:
                problems.append(f"line {number}: hash mismatch (tampered or altered)")
            prev = line["hash"]
        return problems

    def append_raw(self, raw_line: str) -> None:
        """Append a RAW line — used ONLY by the tamper test."""
        with open(self.path, "ab") as handle:
            handle.write((raw_line + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
