"""Shared value types for cross-venue prediction-market arbitrage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BinaryMarketQuote:
    """A point-in-time, two-sided quote for one binary market on one venue.

    ``yes_ask``/``no_ask`` are the prices (dollars, [0, 1]) you would *pay* to
    buy the YES and NO outcomes right now. ``yes_size``/``no_size`` are the
    number of contracts available at that ask. ``no_ask`` is kept explicit
    rather than derived as ``1 - yes_ask`` because real books are not
    symmetric — the whole edge lives in that asymmetry across venues.
    """

    venue: str
    market_key: str
    title: str
    yes_ask: float
    no_ask: float
    yes_size: int
    no_size: int
    event_time_ns: int

    def __post_init__(self) -> None:
        for label, price in (("yes_ask", self.yes_ask), ("no_ask", self.no_ask)):
            if not 0.0 <= price <= 1.0:
                raise ValueError(f"{label}_out_of_range: {price}")
        for label, size in (("yes_size", self.yes_size), ("no_size", self.no_size)):
            if size < 0:
                raise ValueError(f"{label}_negative: {size}")

    def ask_for(self, outcome: str) -> float:
        if outcome == "yes":
            return self.yes_ask
        if outcome == "no":
            return self.no_ask
        raise ValueError(f"unknown_outcome: {outcome!r}")

    def size_for(self, outcome: str) -> int:
        if outcome == "yes":
            return self.yes_size
        if outcome == "no":
            return self.no_size
        raise ValueError(f"unknown_outcome: {outcome!r}")
