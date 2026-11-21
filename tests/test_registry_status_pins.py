"""P16-A-2: pin the registry data_status of ALL 16 models.

F-j (15-V): flipping a registered stub model's data_status to "live"
escaped the whole suite — the per-model evidence string inside predict()
is a separate hard-coded literal (e.g. earnings_drift.py:83) that can
drift independently from the registry entry. This file pins:

1. registry: the four known stubs (earnings_drift,
   fundamental_guardrails, sector_rotation, quality_value) are "stub";
   every other model is NOT "stub";
2. evidence agreement: for every model whose predict() carries a
   hard-coded `"data_status": "..."` evidence literal, that literal must
   EQUAL the registry attribute (source-level scan, so the two can no
   longer drift silently).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Models whose data is still unsourced (P14-B checklist). The 15-V
# brief named the four quant stubs; the registry also pins the four
# India macro models as stubs — pinned as-found (8 total).
EXPECTED_STUBS = frozenset({
    "earnings_drift",
    "fundamental_guardrails",
    "sector_rotation",
    "quality_value",
    "promoter_pledge",
    "block_deals",
    "fii_dii_regime",
    "macro_overlay",
})


def _registry_entries() -> dict[str, dict]:
    from typer.testing import CliRunner

    from niveshdristi.cli.main import app

    result = CliRunner().invoke(app, ["--json", "models"])
    assert result.exit_code == 0, result.output
    models = json.loads(result.output)["models"]
    assert len(models) >= 16, (
        f"non-vacuity: expected >= 16 registered models, got {len(models)}"
    )
    return {m["model_id"]: m for m in models}


def _module_file_for(model_id: str) -> Path | None:
    """Best-effort source file for a model id (quant models live in
    alpha/quant/<name>.py; India models in markets/in_nse/models/)."""
    for base in (
        REPO / "src" / "niveshdristi" / "alpha" / "quant",
        REPO / "src" / "niveshdristi" / "markets" / "in_nse" / "models",
    ):
        for f in base.glob("*.py"):
            text = f.read_text(encoding="utf-8")
            if f'model_id: str = Field(default="{model_id}"' in text or \
               f'"{model_id}"' in text and "class " in text:
                if re.search(rf'"{model_id}"', text) and "registry_entry" in text:
                    return f
    return None


class TestRegistryStatusPins:
    def test_four_stubs_pinned_and_rest_not_stub(self):
        entries = _registry_entries()
        stubs = {mid for mid, m in entries.items()
                 if m["data_status"] == "stub"}
        assert stubs == set(EXPECTED_STUBS), (
            "registry data_status pins drifted: stubs are "
            f"{sorted(stubs)}, expected {sorted(EXPECTED_STUBS)}"
        )

    def test_evidence_literal_agrees_with_registry(self):
        """The predict()-side evidence literal must match the registry
        attribute for every model that carries one (F-j drift guard)."""
        entries = _registry_entries()
        checked = 0
        for mid, entry in entries.items():
            f = _module_file_for(mid)
            if f is None:
                continue
            text = f.read_text(encoding="utf-8")
            hits = re.findall(r'"data_status":\s*"(stub|live|unavailable)"', text)
            if not hits:
                continue
            checked += 1
            for hit in set(hits):
                assert hit == entry["data_status"], (
                    f"{mid}: evidence literal 'data_status: {hit}' in "
                    f"{f.relative_to(REPO)} disagrees with the registry "
                    f"value {entry['data_status']!r} (F-j drift)"
                )
        assert checked >= 4, (
            f"non-vacuity: expected >= 4 evidence-literal checks, got {checked}"
        )
