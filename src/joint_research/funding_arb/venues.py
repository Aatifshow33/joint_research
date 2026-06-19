"""Funding-rate sources for perpetual DEXs reachable without geo-blocks.

The big CEX perps (Binance, Bybit, OKX) geo-block many IPs, so the default live
sources here are **Hyperliquid** and **dYdX** — decentralized perp venues that
are broadly reachable and need no KYC gate. Both settle funding hourly, so the
per-hour rate is directly comparable.

Projection functions are pure and unit-tested; only the ``fetch_*`` helpers
touch the network.
"""

from __future__ import annotations

from typing import Any

from joint_research.funding_arb.types import FundingQuote

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
DYDX_MARKETS_URL = "https://indexer.dydx.trade/v4/perpetualMarkets"


def project_hyperliquid(
    meta_and_ctxs: list[Any],
) -> list[FundingQuote]:
    """Project Hyperliquid ``metaAndAssetCtxs`` into funding quotes (hourly)."""
    if not isinstance(meta_and_ctxs, list) or len(meta_and_ctxs) < 2:
        return []
    universe = meta_and_ctxs[0].get("universe", [])
    ctxs = meta_and_ctxs[1]
    quotes: list[FundingQuote] = []
    for asset, ctx in zip(universe, ctxs, strict=False):
        name = asset.get("name")
        funding = _to_float(ctx.get("funding"))
        mark = _to_float(ctx.get("markPx"))
        if not name or funding is None or mark is None or mark <= 0:
            continue
        quotes.append(
            FundingQuote(
                venue="hyperliquid",
                base=str(name).upper(),
                symbol=str(name).upper(),
                funding_hourly=funding,
                mark_price=mark,
            )
        )
    return quotes


def project_dydx(markets_payload: dict[str, Any]) -> list[FundingQuote]:
    """Project dYdX ``perpetualMarkets`` into funding quotes (hourly)."""
    markets = markets_payload.get("markets", {})
    quotes: list[FundingQuote] = []
    for symbol, market in markets.items():
        if str(market.get("status", "")).upper() not in ("", "ACTIVE"):
            continue
        funding = _to_float(market.get("nextFundingRate"))
        mark = _to_float(market.get("oraclePrice"))
        if funding is None or mark is None or mark <= 0:
            continue
        base = str(symbol).split("-", 1)[0].upper()
        quotes.append(
            FundingQuote(
                venue="dydx",
                base=base,
                symbol=str(symbol),
                funding_hourly=funding,
                mark_price=mark,
            )
        )
    return quotes


def fetch_hyperliquid_quotes(
    *, timeout_seconds: float = 20.0
) -> list[FundingQuote]:  # pragma: no cover - thin network wrapper
    import httpx

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(HYPERLIQUID_INFO_URL, json={"type": "metaAndAssetCtxs"})
        if response.status_code >= 400:
            return []
        body = response.json()
    return project_hyperliquid(body)


def fetch_dydx_quotes(
    *, timeout_seconds: float = 20.0
) -> list[FundingQuote]:  # pragma: no cover - thin network wrapper
    import httpx

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(DYDX_MARKETS_URL)
        if response.status_code >= 400:
            return {}  # type: ignore[return-value]
        body = response.json()
    return project_dydx(body)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
