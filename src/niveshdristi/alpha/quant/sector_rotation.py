"""Sector rotation model — PORT of legacy regime/rrg.py maths, import-only.

PORTED (legacy maths, imported read-only, unchanged):
- niveshdristi.regime.rrg.compute_rrg (line 32): RRG quadrants per sector
  vs the benchmark. NOTE (plain statement): NO legacy golden exists for
  compute_rrg — there is no characterization test for it — so the equality
  test below compares the wrapper against a DIRECT legacy invocation on the
  same synthetic inputs; no golden file pretending legacy correctness is
  created.
- niveshdristi.regime.rrg.market_regime (line 75): bull/bear/choppy state
  (this one IS characterization-covered in tests/test_characterization.py).

NEW (not a port):
- Role-based wiring: sectors arrive as ONE neutral aux frame
  inputs.aux["sector_index"] with columns (sector, date, close); the legacy
  functions expect per-sector frames with an adj_close column, so NEW glue
  builds those views (close copied to adj_close) before the legacy calls.
- Sector tilt emitted through Signal evidence (conviction exactly 0.0:
  tilt is context for other models, not a directional view).
- The legacy SECTOR_ETFS ticker literals are NOT copied here; a verbatim
  UNVERIFIED copy lives in markets/in_nse/model_config.yaml (never probed,
  never used for fetches).

data_status "stub": no verified sector-index data source exists (Phase 2
P0). Constants are UNVALIDATED DEFAULTS; theses state hypotheses only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from niveshdristi.core.alpha import AlphaModel, AsOfContext, ModelInputs, ModelRegistryEntry
from niveshdristi.core.instrument import Instrument
from niveshdristi.core.signal import Signal
from niveshdristi.regime.rrg import compute_rrg, market_regime  # legacy maths (PORT)

# UNVALIDATED DEFAULTS
HORIZON_DAYS = 20
DEFAULT_VIX = 15.0  # legacy market_regime takes a vix float; no VIX source -> default


def _to_adj_close_view(df: pl.DataFrame) -> pl.DataFrame:
    """NEW glue: neutral 'close' column copied to the legacy 'adj_close' name."""
    return df.with_columns(pl.col("close").alias("adj_close"))


def _to_adj_close_benchmark(df: pl.DataFrame) -> pl.DataFrame:
    return _to_adj_close_view(df)


class SectorRotation:
    """RRG sector rotation over the 'sector_index' role frame (PORT + NEW glue)."""

    @property
    def model_id(self) -> str:
        return "sector_rotation"

    async def legacy_quadrants(self, sector_frames: dict, benchmark: pl.DataFrame):
        """Direct legacy call (ported maths), adapted frames in, dict out."""
        return await compute_rrg(
            {name: _to_adj_close_view(df) for name, df in sector_frames.items()},
            _to_adj_close_benchmark(benchmark),
        )

    def legacy_state(self, benchmark: pl.DataFrame, vix: float = DEFAULT_VIX) -> str:
        """Direct legacy call (ported maths, characterization-covered)."""
        return market_regime(_to_adj_close_benchmark(benchmark), vix)

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        sector_frame = inputs.aux.get("sector_index")
        benchmark = inputs.aux.get("benchmark")
        if not isinstance(sector_frame, pl.DataFrame) or not isinstance(benchmark, pl.DataFrame):
            return []
        if not {"sector", "date", "close"}.issubset(sector_frame.columns):
            return []
        if "close" not in benchmark.columns:
            return []

        sector_frames = {
            name: _to_adj_close_view(g.drop("sector"))
            for name, g in sector_frame.partition_by("sector", as_dict=True).items()
        }
        quadrants = _run_async(self.legacy_quadrants(sector_frames, benchmark))
        state = self.legacy_state(benchmark)

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
                    conviction=0.0,  # evidence-only: sector tilt is context, not a view
                    horizon_days=HORIZON_DAYS,
                    thesis=(
                        "EVIDENCE-ONLY (no directional view): hypothesized sector "
                        "rotation quadrants vs the benchmark (ported legacy maths); "
                        "sector tilt is context for other models."
                    ),
                    evidence={
                        "market_state": state,
                        "sector_count": len(quadrants),
                        "data_status": "stub",
                    },
                    metadata={
                        "sector_quadrants": {
                            str(k): str(v) for k, v in sorted(quadrants.items())
                        },
                    },
                    model_id=self.model_id,
                )
            )
        return signals

    def registry_entry(self) -> ModelRegistryEntry:
        return ModelRegistryEntry(
            model_id=self.model_id,
            horizon_days=HORIZON_DAYS,
            required_data=("prices",),  # via 'sector_index' and 'benchmark' roles
            pit_safe=True,
            data_status="stub",  # no verified sector-index source
            description="PORT of legacy compute_rrg/market_regime (import-only; no "
            "legacy golden exists for compute_rrg) with NEW role-based glue; emits "
            "sector tilt as evidence, conviction always 0.0.",
        )


def _run_async(coro):
    """Run the legacy async compute_rrg synchronously (NEW glue)."""
    import asyncio

    return asyncio.run(coro)


# mypy enforces the predict(ctx, inputs) signature at module level
_: AlphaModel = SectorRotation()
