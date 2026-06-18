"""Cross-venue prediction-market arbitrage detection.

This package is a *research / detection* layer. It does not place orders. Its
job is to answer the question that decides whether the strategy is worth wiring
to live capital at all: **how often do cross-venue prediction-market spreads
clear realistic, fee-aware thresholds at sizes a small account can actually
fill?**

The design keeps three concerns separated so the economics stay testable
without any network access:

* ``fees`` / ``types`` / ``detector`` / ``matcher`` are pure, deterministic
  logic over plain dataclasses.
* ``kalshi_client`` / ``polymarket_quotes`` isolate the venue-specific I/O and
  payload projection. The projection functions are pure and unit-tested; only
  the thin fetchers touch the network.
* ``scan`` orchestrates a single detection pass and writes warehouse-style
  artifacts.
"""

from joint_research.predmarket_arb.detector import (
    ArbEvaluation,
    DetectorConfig,
    evaluate_market_pair,
)
from joint_research.predmarket_arb.fees import (
    KALSHI_GENERAL_FEE_RATE,
    KalshiFeeModel,
    PolymarketFeeModel,
    VenueFeeModel,
)
from joint_research.predmarket_arb.matcher import MatchedMarket, match_markets
from joint_research.predmarket_arb.types import BinaryMarketQuote

__all__ = [
    "ArbEvaluation",
    "BinaryMarketQuote",
    "DetectorConfig",
    "KALSHI_GENERAL_FEE_RATE",
    "KalshiFeeModel",
    "MatchedMarket",
    "PolymarketFeeModel",
    "VenueFeeModel",
    "evaluate_market_pair",
    "match_markets",
]
