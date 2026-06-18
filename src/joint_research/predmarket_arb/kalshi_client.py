"""Kalshi market quotes.

Kalshi's public ``/trade-api/v2/markets`` endpoint returns prices in **cents**
(integer 1..99). To buy YES you pay ``yes_ask``; to buy NO you pay ``no_ask``.
``*_ask`` of 0 means "no resting offer", which we treat as unavailable.

The payload projection (``project_kalshi_market``) is pure and unit-tested. The
network fetch (``fetch_kalshi_markets``) is a thin wrapper kept out of the
tested path so the economics never depend on a live endpoint.
"""

from __future__ import annotations

from typing import Any

from joint_research.predmarket_arb.types import BinaryMarketQuote

KALSHI_MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"


def project_kalshi_market(
    payload: dict[str, Any],
    *,
    event_time_ns: int,
) -> BinaryMarketQuote | None:
    """Project one Kalshi market payload into a quote, or ``None`` if unusable.

    A market is unusable for arb if it is not open, has no ticker, or has no
    two-sided offer (one of the asks is missing/zero).
    """

    ticker = payload.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return None
    if str(payload.get("status", "")).lower() not in ("", "active", "open"):
        return None

    yes_ask = _cents_to_dollars(payload.get("yes_ask"))
    no_ask = _cents_to_dollars(payload.get("no_ask"))
    if yes_ask is None or no_ask is None or yes_ask <= 0.0 or no_ask <= 0.0:
        return None

    title = _first_str(payload, ("title", "subtitle", "yes_sub_title")) or ticker

    return BinaryMarketQuote(
        venue="kalshi",
        market_key=ticker.strip(),
        title=title,
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_size=_optional_int(payload.get("yes_ask_size")) or _default_size(),
        no_size=_optional_int(payload.get("no_ask_size")) or _default_size(),
        event_time_ns=event_time_ns,
    )


def project_kalshi_markets(
    payloads: list[dict[str, Any]],
    *,
    event_time_ns: int,
) -> list[BinaryMarketQuote]:
    quotes: list[BinaryMarketQuote] = []
    for payload in payloads:
        quote = project_kalshi_market(payload, event_time_ns=event_time_ns)
        if quote is not None:
            quotes.append(quote)
    return quotes


def fetch_kalshi_markets(
    *,
    limit: int = 200,
    status: str = "open",
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:  # pragma: no cover - thin network wrapper
    """Fetch open Kalshi markets. Imported lazily so offline tests stay clean."""
    import httpx

    params = {"limit": str(limit), "status": status}
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(KALSHI_MARKETS_URL, params=params)
        response.raise_for_status()
        body = response.json()
    markets = body.get("markets")
    return list(markets) if isinstance(markets, list) else []


def _cents_to_dollars(value: Any) -> float | None:
    if value is None:
        return None
    try:
        cents = float(value)
    except (TypeError, ValueError):
        return None
    if cents < 0:
        return None
    return cents / 100.0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _default_size() -> int:
    # When the venue omits depth we assume a single contract is available so
    # liquidity never silently inflates a phantom fill.
    return 1
