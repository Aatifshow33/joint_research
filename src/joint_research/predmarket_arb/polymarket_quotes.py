"""Polymarket binary-market quotes.

Polymarket's Gamma ``/markets`` payload carries ``outcomes`` and
``outcomePrices`` (often as JSON-encoded strings) plus an ``orderMinSize`` and
liquidity. For a binary YES/NO market the two outcome prices are the mid/last
marks; we treat the YES price as the YES ask and ``1 - yes`` as the NO ask when
an explicit NO price is absent. The projection is pure; reuse of the warehouse
``polymarket_crypto_markets`` table is layered on top via ``quote_from_market_row``.
"""

from __future__ import annotations

import json
from typing import Any

from joint_research.predmarket_arb.types import BinaryMarketQuote

# The Gamma /markets payload does NOT carry order-book depth — real fillable
# size needs the CLOB book (a documented follow-up). Until then we assume a
# fixed available depth so the *bankroll* constraint, not a phantom depth of 1,
# is what binds a small account. Override per-market once real depth is wired.
_DEFAULT_SIZE = 500


def project_polymarket_market(
    payload: dict[str, Any],
    *,
    event_time_ns: int,
) -> BinaryMarketQuote | None:
    """Project one Gamma market payload into a quote, or ``None`` if unusable."""

    market_key = _first_str(payload, ("conditionId", "id", "slug"))
    if market_key is None:
        return None
    if payload.get("closed") is True or payload.get("active") is False:
        return None

    prices = _parse_string_list_as_floats(payload.get("outcomePrices"))
    outcomes = [str(item) for item in _parse_string_list(payload.get("outcomes"))]
    yes_ask, no_ask = _yes_no_from_outcomes(outcomes, prices)
    if yes_ask is None:
        return None
    if no_ask is None:
        no_ask = round(1.0 - yes_ask, 6)
    if not (0.0 < yes_ask < 1.0) or not (0.0 < no_ask < 1.0):
        return None

    title = _first_str(payload, ("question", "title", "slug")) or market_key
    size = _size_from_liquidity(payload)

    return BinaryMarketQuote(
        venue="polymarket",
        market_key=market_key,
        title=title,
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_size=size,
        no_size=size,
        event_time_ns=event_time_ns,
    )


def quote_from_market_row(
    *,
    market_key: str,
    title: str,
    yes_price: float,
    no_price: float | None,
    size: int,
    event_time_ns: int,
) -> BinaryMarketQuote:
    """Build a quote from already-extracted fields (e.g. a warehouse row)."""
    resolved_no = no_price if no_price is not None else round(1.0 - yes_price, 6)
    return BinaryMarketQuote(
        venue="polymarket",
        market_key=market_key,
        title=title,
        yes_ask=yes_price,
        no_ask=resolved_no,
        yes_size=size,
        no_size=size,
        event_time_ns=event_time_ns,
    )


def project_polymarket_markets(
    payloads: list[dict[str, Any]],
    *,
    event_time_ns: int,
) -> list[BinaryMarketQuote]:
    quotes: list[BinaryMarketQuote] = []
    for payload in payloads:
        quote = project_polymarket_market(payload, event_time_ns=event_time_ns)
        if quote is not None:
            quotes.append(quote)
    return quotes


def _yes_no_from_outcomes(
    outcomes: list[str],
    prices: list[float],
) -> tuple[float | None, float | None]:
    if len(prices) < 2 or len(outcomes) < 2:
        # Single price still lets us read a YES mark if present.
        if prices:
            return prices[0], None
        return None, None
    yes_index = _index_of(outcomes, "yes")
    no_index = _index_of(outcomes, "no")
    if yes_index is not None and no_index is not None:
        return prices[yes_index], prices[no_index]
    # Fall back to positional ordering [YES, NO].
    return prices[0], prices[1]


def _index_of(outcomes: list[str], label: str) -> int | None:
    for index, outcome in enumerate(outcomes):
        if outcome.strip().lower() == label:
            return index
    return None


def _parse_string_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return list(decoded)
    return []


def _parse_string_list_as_floats(value: Any) -> list[float]:
    floats: list[float] = []
    for item in _parse_string_list(value):
        try:
            floats.append(float(item))
        except (TypeError, ValueError):
            return []
    return floats


def _size_from_liquidity(payload: dict[str, Any]) -> int:
    # An explicit ``available_size`` (e.g. injected from a CLOB book snapshot)
    # wins; otherwise fall back to the assumed default depth.
    value = payload.get("available_size")
    try:
        if value is not None:
            size = int(float(value))
            if size > 0:
                return size
    except (TypeError, ValueError):
        pass
    return _DEFAULT_SIZE


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
