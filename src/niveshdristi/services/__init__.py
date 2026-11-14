"""services/ — UI-facing composition layer (NEW, P8-S1).

A thin, read-mostly facade over the paper fund, reports, registry and
validation results. Rules (binding, tested):
- MAY import: core/, paper/, markets/ (labels only), engine/ (read-only
  result objects), stdlib, pydantic.
- MUST NEVER import: execution/ (brokers, orders), portfolio/ (targets,
  gates), llm/, ui/ (or any UI framework).
Every returned payload carries an as-of date taken from the DATA (never
the clock) and the DataLimitations banner.
"""

from niveshdristi.services.fund import read_fund
from niveshdristi.services.labels import market_labels

__all__ = ["read_fund", "market_labels"]
