"""Real order-book depth for trustworthy position sizing.

The Gamma ``/markets`` payload gives a top-of-book mark but no depth, so the
broad scan assumes a fixed available size. Before acting on any candidate we
want the *real* fillable size: how many contracts can actually be bought at or
under the price the arb assumes. This module computes that from the Polymarket
CLOB book.

``fillable_size_at_or_below`` is pure and unit-tested; ``fetch_polymarket_book``
is the only network touch and is kept out of the tested path.
"""

from __future__ import annotations

from typing import Any

POLYMARKET_CLOB_BOOK_URL = "https://clob.polymarket.com/book"


def fillable_size_at_or_below(
    asks: list[dict[str, Any]],
    *,
    max_price: float,
) -> int:
    """Total ask size buyable at a price <= ``max_price`` (contracts, floored).

    ``asks`` is a CLOB book ``asks`` array of ``{"price": str, "size": str}``.
    A buyer crossing the spread fills the cheapest asks first, so every ask at
    or below the acceptable price contributes its full size.
    """
    total = 0.0
    for level in asks:
        price = _to_float(level.get("price"))
        size = _to_float(level.get("size"))
        if price is None or size is None or size <= 0:
            continue
        if price <= max_price + 1e-9:
            total += size
    return int(total)


def fetch_polymarket_book(
    token_id: str,
    *,
    client: Any | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:  # pragma: no cover - thin network wrapper
    """Fetch one CLOB book by token id, optionally reusing an httpx client."""
    import httpx

    active = client if client is not None else httpx.Client(timeout=timeout_seconds)
    try:
        response = active.get(POLYMARKET_CLOB_BOOK_URL, params={"token_id": token_id})
        if response.status_code >= 400:
            return {}
        body = response.json()
    except httpx.HTTPError:
        return {}
    finally:
        if client is None:
            active.close()
    return body if isinstance(body, dict) else {}


def polymarket_fillable_size(
    token_id: str,
    *,
    max_price: float,
    client: Any | None = None,
    timeout_seconds: float = 8.0,
) -> int | None:  # pragma: no cover - thin network wrapper
    """Live fillable size for ``token_id`` at or below ``max_price``."""
    book = fetch_polymarket_book(token_id, client=client, timeout_seconds=timeout_seconds)
    asks = book.get("asks")
    if not isinstance(asks, list):
        return None
    return fillable_size_at_or_below(asks, max_price=max_price)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
