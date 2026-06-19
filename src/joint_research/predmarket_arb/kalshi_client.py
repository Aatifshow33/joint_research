"""Kalshi market quotes.

Kalshi's public API exposes prices as dollar strings in the ``*_dollars`` fields
(e.g. ``yes_ask_dollars: "0.18"``) and resting depth in the ``*_size_fp`` fields.
Older payloads used integer **cents** in ``yes_ask``/``no_ask``; the projection
accepts both so fixtures and live data share one code path. To buy YES you pay
``yes_ask``; to buy NO you pay ``no_ask``. A zero/absent ask means "no resting
offer", which we treat as unavailable.

The liquid, tradeable markets (Politics, Elections, Financials, Economics, …)
live under *events*; the flat ``/markets`` feed is dominated by auto-generated
sports parlays, so the live fetch pages the ``/events`` endpoint with nested
markets. ``liquidity_dollars`` is frequently ``0`` even on two-sided markets, so
usability is judged by real asks and ask depth, not that field.

Payload projection is pure and unit-tested; only ``fetch_kalshi_markets`` and
``fetch_kalshi_event_markets`` touch the network.
"""

from __future__ import annotations

from typing import Any

from joint_research.predmarket_arb.types import BinaryMarketQuote

KALSHI_MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
KALSHI_EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"


def project_kalshi_market(
    payload: dict[str, Any],
    *,
    event_time_ns: int,
) -> BinaryMarketQuote | None:
    """Project one Kalshi market payload into a quote, or ``None`` if unusable.

    Unusable for arb if it is not open, has no ticker, or lacks a two-sided
    offer (a missing/zero ask on either side).
    """

    ticker = payload.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return None
    if str(payload.get("status", "")).lower() not in ("", "active", "open"):
        return None

    yes_ask = _read_price(payload, "yes_ask")
    no_ask = _read_price(payload, "no_ask")
    if yes_ask is None or no_ask is None or yes_ask <= 0.0 or no_ask <= 0.0:
        return None
    if yes_ask >= 1.0 or no_ask >= 1.0:
        return None

    title = _first_str(payload, ("title", "yes_sub_title", "subtitle")) or ticker

    return BinaryMarketQuote(
        venue="kalshi",
        market_key=ticker.strip(),
        title=title,
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_size=_read_size(payload, "yes_ask"),
        no_size=_read_size(payload, "no_ask"),
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


def fetch_kalshi_event_markets(
    *,
    max_pages: int = 30,
    page_limit: int = 200,
    timeout_seconds: float = 30.0,
) -> list[dict[str, Any]]:  # pragma: no cover - thin network wrapper
    """Page open events with nested markets and flatten to market payloads."""
    import httpx

    markets: list[dict[str, Any]] = []
    cursor: str | None = None
    with httpx.Client(timeout=timeout_seconds) as client:
        for _ in range(max_pages):
            params = {
                "limit": str(page_limit),
                "status": "open",
                "with_nested_markets": "true",
            }
            if cursor:
                params["cursor"] = cursor
            response = client.get(KALSHI_EVENTS_URL, params=params)
            response.raise_for_status()
            body = response.json()
            for event in body.get("events", []):
                for market in event.get("markets", []):
                    markets.append(market)
            cursor = body.get("cursor")
            if not cursor:
                break
    return markets


def fetch_kalshi_markets(
    *,
    timeout_seconds: float = 25.0,
) -> list[dict[str, Any]]:  # pragma: no cover - thin network wrapper
    """Fetch usable open Kalshi markets (via the events endpoint)."""
    return fetch_kalshi_event_markets(timeout_seconds=timeout_seconds)


def _read_price(payload: dict[str, Any], side: str) -> float | None:
    """Prefer the dollar field; fall back to the legacy cents field."""
    dollars = _optional_float(payload.get(f"{side}_dollars"))
    if dollars is not None:
        return dollars if dollars >= 0 else None
    cents = _optional_float(payload.get(side))
    if cents is None or cents < 0:
        return None
    return cents / 100.0


def _read_size(payload: dict[str, Any], side: str) -> int:
    for key in (f"{side}_size_fp", f"{side}_size"):
        value = _optional_float(payload.get(key))
        if value is not None and value >= 0:
            return int(value)
    return _default_size()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _default_size() -> int:
    # When depth is absent we assume a single contract so a phantom fill never
    # silently inflates available size.
    return 1
