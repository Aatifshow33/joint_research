"""Value types for delta-neutral funding-rate arbitrage."""

from __future__ import annotations

from dataclasses import dataclass

HOURS_PER_YEAR = 24 * 365


@dataclass(frozen=True)
class FundingQuote:
    """A venue's current funding for one perpetual market.

    ``funding_hourly`` is normalized to a per-hour rate (fraction of notional),
    regardless of each venue's native settlement interval. Positive funding
    means longs pay shorts — so a short position *earns* it.
    """

    venue: str
    base: str
    symbol: str
    funding_hourly: float
    mark_price: float

    @property
    def funding_apr(self) -> float:
        """Naive annualized rate from the current hourly snapshot."""
        return self.funding_hourly * HOURS_PER_YEAR

    def short_earns_apr(self) -> float:
        """APR a delta-hedged short on this venue would earn from funding."""
        return self.funding_apr

    def long_earns_apr(self) -> float:
        """APR a delta-hedged long on this venue would earn (negative of funding)."""
        return -self.funding_apr
