"""Cross-venue delta-neutral funding-rate opportunity scanner.

For a coin quoted on two venues, going **long the lower-funding venue and short
the higher-funding venue** in equal size is price-neutral and earns the funding
*spread*. The spread is always captured in the favorable direction by
construction, so the gross rate is non-negative; the real questions are whether
it clears trading fees and whether it is sustainable.

Two honesty guardrails are built in:

* a single hourly snapshot annualized is wildly optimistic (funding mean-reverts
  fast), so we report a configurable ``haircut`` and a discounted "realistic"
  APR alongside the raw one;
* extreme rates live on illiquid alts, so ``major_only`` restricts to a safe set.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from joint_research.funding_arb.types import HOURS_PER_YEAR, FundingQuote

# Liquid majors where delta-neutral funding capture is least likely to be a trap.
MAJOR_BASES = frozenset({"BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "LTC", "BNB"})

# Per-leg taker fee defaults (fraction of notional) for the reachable perp DEXs.
DEFAULT_TAKER_FEE = 0.0005  # 0.05%


@dataclass(frozen=True)
class FundingOpportunity:
    """One delta-neutral cross-venue funding position."""

    base: str
    long_venue: str
    short_venue: str
    long_funding_hourly: float
    short_funding_hourly: float
    spread_hourly: float
    gross_apr: float
    realistic_apr: float
    fee_round_trip: float
    breakeven_hours: float
    mark_price: float


def scan_funding_opportunities(
    quotes: list[FundingQuote],
    *,
    taker_fee: float = DEFAULT_TAKER_FEE,
    haircut: float = 0.5,
    major_only: bool = True,
    min_realistic_apr: float = 0.05,
) -> list[FundingOpportunity]:
    """Rank cross-venue delta-neutral funding opportunities.

    ``haircut`` discounts the snapshot APR to a "realistic" sustained estimate
    (0.5 = assume only half the current spread persists). ``taker_fee`` is the
    per-leg fee; a round trip pays it on open and close of both legs (x4).
    """
    if not 0.0 <= haircut <= 1.0:
        raise ValueError(f"haircut_out_of_range: {haircut}")

    by_base: dict[str, list[FundingQuote]] = defaultdict(list)
    for quote in quotes:
        if major_only and quote.base not in MAJOR_BASES:
            continue
        by_base[quote.base].append(quote)

    fee_round_trip = 4.0 * taker_fee
    opportunities: list[FundingOpportunity] = []
    for base, base_quotes in by_base.items():
        if len(base_quotes) < 2:
            continue
        # Short the highest funding, long the lowest funding.
        short_leg = max(base_quotes, key=lambda q: q.funding_hourly)
        long_leg = min(base_quotes, key=lambda q: q.funding_hourly)
        if short_leg.venue == long_leg.venue:
            continue
        spread = short_leg.funding_hourly - long_leg.funding_hourly
        if spread <= 0:
            continue
        gross_apr = spread * HOURS_PER_YEAR
        realistic_apr = gross_apr * (1.0 - haircut)
        if realistic_apr < min_realistic_apr:
            continue
        breakeven_hours = fee_round_trip / spread if spread > 0 else float("inf")
        opportunities.append(
            FundingOpportunity(
                base=base,
                long_venue=long_leg.venue,
                short_venue=short_leg.venue,
                long_funding_hourly=long_leg.funding_hourly,
                short_funding_hourly=short_leg.funding_hourly,
                spread_hourly=spread,
                gross_apr=gross_apr,
                realistic_apr=realistic_apr,
                fee_round_trip=fee_round_trip,
                breakeven_hours=breakeven_hours,
                mark_price=short_leg.mark_price,
            )
        )

    opportunities.sort(key=lambda o: -o.realistic_apr)
    return opportunities
