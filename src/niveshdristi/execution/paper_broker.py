"""PaperBroker (NEW, Phase 4) — local-state-only Broker implementation.

In-memory state with an OPTIONAL local JSON file under a CALLER-SUPPLIED
path (tests use tmp_path). No network, no real orders. Floats are acceptable
for v1 simulation; the Phase 6 ledger must move to integer minor units or
Decimal (documented in docs/PROGRESS.md).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from niveshdristi.core.decision import Fill, Order
from niveshdristi.core.market_rules import PriceLimitRule, RateSchedule
from niveshdristi.execution.sim_broker import ExecutionResult, SimBroker


class PaperBroker:
    """SimBroker-backed paper trading with persisted fills (local only)."""

    def __init__(
        self,
        *,
        rates: RateSchedule,
        price_limits: PriceLimitRule,
        settlement_days: int = 1,
        state_path: str | Path | None = None,
    ) -> None:
        self._sim = SimBroker(
            rates=rates, price_limits=price_limits, settlement_days=settlement_days
        )
        self._state_path = Path(state_path) if state_path else None
        self.fills: list[dict[str, Any]] = []
        self.cash: float | None = None
        if self._state_path and self._state_path.exists():
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            self.fills = data.get("fills", [])
            self.cash = data.get("cash")

    def execute(
        self,
        orders: list[Order],
        *,
        prices: dict[str, float],
        reference_prices: dict[str, float] | None = None,
        advs: dict[str, float] | None = None,
    ) -> list[ExecutionResult]:
        results = self._sim.execute(
            orders,
            prices=prices,
            reference_prices=reference_prices,
            advs=advs,
            cash=self.cash,
        )
        for r in results:
            if r.filled and r.fill is not None:
                self.fills.append(self._fill_to_dict(r.fill))
        self._persist()
        return results

    @staticmethod
    def _fill_to_dict(fill: Fill) -> dict[str, Any]:
        return {
            "symbol": fill.order.instrument.symbol,
            "side": str(fill.order.side),
            "quantity": fill.filled_quantity,
            "fill_price": fill.fill_price,
            "commission": fill.commission,
            "fees": fill.fees,
            "fill_time": fill.fill_time.isoformat(),
        }

    def _persist(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat()
        payload = {"fills": self.fills, "cash": self.cash, "saved_at": now}
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
