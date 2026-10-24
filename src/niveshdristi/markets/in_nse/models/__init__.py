"""IN_NSE-specific alpha models (literal-free by design; symbols live in YAML).

Population mechanism: market packs expose register_all(registry), called from
a composition point OUTSIDE this package (CLI startup / engine bootstrap /
tests). The neutral alpha/registry never imports this package.
"""

from __future__ import annotations

from niveshdristi.alpha.registry import ModelRegistry
from niveshdristi.core.alpha import AlphaModel, ModelRegistryEntry


def entries() -> list[ModelRegistryEntry]:
    """Registry entries for every IN_NSE model in this package."""
    from niveshdristi.markets.in_nse.models.block_deals import BlockDeals
    from niveshdristi.markets.in_nse.models.delivery_anomaly import DeliveryAnomaly
    from niveshdristi.markets.in_nse.models.fii_dii_regime import FiiDiiRegime
    from niveshdristi.markets.in_nse.models.promoter_pledge import PromoterPledge

    models: list[AlphaModel] = [
        DeliveryAnomaly(),
        PromoterPledge(),
        FiiDiiRegime(),
        BlockDeals(),
    ]
    return [m.registry_entry() for m in models]


def register_all(registry: ModelRegistry) -> None:
    """Register every IN_NSE model entry into a registry."""
    registry.register_all(entries())
