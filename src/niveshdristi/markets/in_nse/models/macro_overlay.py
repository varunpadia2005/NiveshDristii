"""Macro overlay model — NEW code, DATA STUB (direction-only).

Consumes a neutral aux frame by ROLE: inputs.aux["macro"] with columns
(factor, date, direction) where direction is a signed -1/0/+1 view per
factor (e.g. repo-rate direction, FX direction, crude direction — supplied
by a future macro source; none exists today). Sector sensitivities come
from markets/in_nse/model_config.yaml — DIRECTION ONLY (+1/0/-1), every
entry an UNVERIFIED economic assumption; no magnitudes exist anywhere.

Emits an EVIDENCE-ONLY signal (conviction exactly 0.0) carrying the sector
tilt map for downstream layers. data_status "stub": no macro source is
wired. Constants are UNVALIDATED DEFAULTS; theses state hypotheses only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import yaml

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal

# UNVALIDATED DEFAULTS
HORIZON_DAYS = 20

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "model_config.yaml"


def load_sector_sensitivity(path: Path = _CONFIG_PATH) -> dict:
    """Direction-only sector sensitivity map from the UNVERIFIED YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sensitivity = data.get("macro_sector_sensitivity", {})
    if not isinstance(sensitivity, dict) or not sensitivity:
        raise ValueError(f"macro_sector_sensitivity missing/empty in {path}")
    return sensitivity


class MacroOverlay:
    """Direction-only macro overlay over the 'macro' role frame (NEW, stub)."""

    @property
    def model_id(self) -> str:
        return "macro_overlay"

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        frame = inputs.aux.get("macro")
        if not isinstance(frame, pl.DataFrame):
            return []
        if not {"factor", "date", "direction"}.issubset(frame.columns):
            return []
        sensitivity = load_sector_sensitivity()

        cutoff = inputs.as_of.isoformat()
        recent = frame.filter(pl.col("date").cast(pl.String).str.slice(0, 10) <= cutoff)
        directions = {
            str(f): int(d)
            for f, d in zip(recent["factor"].to_list(), recent["direction"].to_list(), strict=False)
        }

        # Sector tilt: sum of factor directions weighted by the direction-only
        # sensitivity signs. Result is a signed int per sector — a TILT, not a
        # magnitude-calibrated score.
        tilt: dict[str, int] = {}
        for factor, fdir in directions.items():
            for sector, sdir in sensitivity.get(factor, {}).items():
                tilt[sector] = tilt.get(sector, 0) + int(sdir) * fdir

        stamp: datetime = ctx.as_of if ctx.as_of.tzinfo else ctx.as_of.replace(tzinfo=UTC)
        signals: list[Signal] = []
        for symbol in inputs.prices:
            signals.append(
                Signal(
                    instrument=Instrument(
                        symbol=symbol,
                        exchange=ctx.market_id,
                        market_id=ctx.market_id,
                        currency="XXX",
                    ),
                    as_of=stamp,
                    conviction=0.0,  # evidence-only: a tilt map, not a view
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        "EVIDENCE-ONLY (no directional view): direction-only sector "
                        "tilt from macro factor directions; all sensitivities are "
                        "UNVERIFIED economic assumptions."
                    ),
                    evidence={
                        "factor_count": len(directions),
                        "data_status": "stub",
                    },
                    metadata={
                        "factor_directions": dict(sorted(directions.items())),
                        "sector_tilt": dict(sorted(tilt.items())),
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),  # macro arrives via the 'macro' aux role
            pit_safe=True,
            data_status="stub",
            description="NEW (stub): direction-only macro overlay with UNVERIFIED "
            "sector sensitivities from model_config.yaml; emits a tilt map as "
            "evidence, conviction always 0.0.",
        )


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = MacroOverlay()
