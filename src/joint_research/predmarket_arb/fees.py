"""Venue fee models for prediction-market arbitrage.

Fees are the entire game here. A naive "sum of YES + NO < $1" check overstates
edge badly because Kalshi's trading fee is large and *non-linear* in price (it
peaks at the 50c midpoint), and it rounds up to the next cent per fill.

All prices are expressed in dollars in [0, 1]; one contract resolves to $1 or
$0. Fee functions return the total fee in dollars for buying ``contracts`` of a
single side at ``price``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

# Kalshi's published general trading-fee rate. The per-fill fee is
# ``ceil_to_cent(rate * contracts * price * (1 - price))``. A handful of
# markets (e.g. some index products) use a lower rate; callers can override.
KALSHI_GENERAL_FEE_RATE = 0.07

# Polymarket currently charges no taker trading fee. Settlement is gasless for
# end users via the relayer, but we keep a configurable flat per-order cost so
# the model can absorb gas/relayer assumptions without code changes.
POLYMARKET_DEFAULT_TAKER_FEE_RATE = 0.0
POLYMARKET_DEFAULT_FLAT_ORDER_COST = 0.0


class VenueFeeModel(Protocol):
    """A venue's taker fee for buying one side of a binary market."""

    @property
    def venue(self) -> str:
        """Venue name (read-only)."""
        ...

    def taker_fee(self, *, price: float, contracts: int) -> float:
        """Total fee in dollars to buy ``contracts`` at ``price``."""
        ...


@dataclass(frozen=True)
class KalshiFeeModel:
    """Kalshi general trading fee: ``ceil_to_cent(rate * C * P * (1 - P))``."""

    venue: str = "kalshi"
    rate: float = KALSHI_GENERAL_FEE_RATE

    def taker_fee(self, *, price: float, contracts: int) -> float:
        _validate_inputs(price=price, contracts=contracts)
        if contracts == 0:
            return 0.0
        raw = self.rate * contracts * price * (1.0 - price)
        return _ceil_to_cent(raw)


@dataclass(frozen=True)
class PolymarketFeeModel:
    """Polymarket taker fee: linear rate plus an optional flat per-order cost."""

    venue: str = "polymarket"
    rate: float = POLYMARKET_DEFAULT_TAKER_FEE_RATE
    flat_order_cost: float = POLYMARKET_DEFAULT_FLAT_ORDER_COST

    def taker_fee(self, *, price: float, contracts: int) -> float:
        _validate_inputs(price=price, contracts=contracts)
        if contracts == 0:
            return 0.0
        return self.rate * contracts * price + self.flat_order_cost


def fee_model_for_venue(venue: str) -> VenueFeeModel:
    """Return the default fee model for a known venue name."""
    normalized = venue.strip().lower()
    if normalized == "kalshi":
        return KalshiFeeModel()
    if normalized == "polymarket":
        return PolymarketFeeModel()
    raise ValueError(f"no_fee_model_for_venue: {venue!r}")


def _ceil_to_cent(value: float) -> float:
    """Round a dollar amount up to the next cent (Kalshi rounds fees up)."""
    return math.ceil(round(value * 100, 6)) / 100.0


def _validate_inputs(*, price: float, contracts: int) -> None:
    if not 0.0 <= price <= 1.0:
        raise ValueError(f"price_out_of_range: {price}")
    if contracts < 0:
        raise ValueError(f"contracts_negative: {contracts}")
