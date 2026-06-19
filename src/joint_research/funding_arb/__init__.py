"""Delta-neutral funding-rate arbitrage: the safe compounding engine.

Market-neutral (no directional bet), recycles capital continuously (funding
settles hourly), and pairs with a monthly-contribution plan to compound a small
stake. Default live sources are the geo-reachable perp DEXs (Hyperliquid, dYdX);
the big CEXs are blocked from many IPs.

Pure logic (``types``, ``scanner``, ``plan``) is unit-tested; only ``venues``
fetchers and the CLI touch the network.
"""

from joint_research.funding_arb.plan import (
    GrowthPlan,
    monthly_contribution_for_target,
    project_growth,
)
from joint_research.funding_arb.scanner import (
    FundingOpportunity,
    scan_funding_opportunities,
)
from joint_research.funding_arb.types import FundingQuote

__all__ = [
    "FundingOpportunity",
    "FundingQuote",
    "GrowthPlan",
    "monthly_contribution_for_target",
    "project_growth",
    "scan_funding_opportunities",
]
