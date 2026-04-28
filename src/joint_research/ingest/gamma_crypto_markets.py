"""Ingest Polymarket crypto-tagged markets via the Gamma /markets endpoint.

Polymarket tags crypto markets with ``tag_id=21``. The /markets endpoint is
read-only and returns a flat list of market objects with ``clobTokenIds`` —
exactly the token IDs we need to drive ``/prices-history`` ingestion.

This module is venue-agnostic at the projection layer: any future change to
which crypto tag we ingest is parameterized.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import httpx

from joint_research.warehouse.schema import POLYMARKET_CRYPTO_MARKETS

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_CRYPTO_TAG_ID = 21
GAMMA_SOURCE = "gamma.markets.crypto"


@dataclass(frozen=True)
class CryptoMarketRow:
    market_id: str
    event_time_ns: int
    payload_hash: str
    payload_json: str
    condition_id: str | None
    question: str | None
    slug: str | None
    event_id: str | None
    yes_token_id: str | None
    no_token_id: str | None
    active: bool | None
    closed: bool | None
    archived: bool | None
    end_date_iso: str | None
    volume_total_usd: float | None
    volume_24h_usd: float | None
    volume_1wk_usd: float | None
    volume_1mo_usd: float | None
    liquidity_usd: float | None
    last_trade_price: float | None
    crypto_asset_tag: str | None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": GAMMA_SOURCE,
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "question": self.question,
            "slug": self.slug,
            "event_id": self.event_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "active": self.active,
            "closed": self.closed,
            "archived": self.archived,
            "end_date_iso": self.end_date_iso,
            "volume_total_usd": self.volume_total_usd,
            "volume_24h_usd": self.volume_24h_usd,
            "volume_1wk_usd": self.volume_1wk_usd,
            "volume_1mo_usd": self.volume_1mo_usd,
            "liquidity_usd": self.liquidity_usd,
            "last_trade_price": self.last_trade_price,
            "crypto_asset_tag": self.crypto_asset_tag,
        }


def project_gamma_market_payload(
    payload: dict[str, Any],
    *,
    fetched_at: datetime,
) -> CryptoMarketRow:
    market_id = payload.get("id")
    if market_id is None:
        raise ValueError("gamma_market_missing_id")
    market_id_str = str(market_id)

    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    yes_token, no_token = _extract_yes_no_tokens(payload)
    event_time_ns = _event_time_ns(payload, fallback=fetched_at)

    return CryptoMarketRow(
        market_id=market_id_str,
        event_time_ns=event_time_ns,
        payload_hash=payload_hash,
        payload_json=payload_json,
        condition_id=_optional_str(payload.get("conditionId")),
        question=_optional_str(payload.get("question")),
        slug=_optional_str(payload.get("slug")),
        event_id=_event_id_from_market(payload),
        yes_token_id=yes_token,
        no_token_id=no_token,
        active=_optional_bool(payload.get("active")),
        closed=_optional_bool(payload.get("closed")),
        archived=_optional_bool(payload.get("archived")),
        end_date_iso=_optional_str(payload.get("endDate") or payload.get("endDateIso")),
        volume_total_usd=_optional_float(payload.get("volume")),
        volume_24h_usd=_optional_float(payload.get("volume24hr")),
        volume_1wk_usd=_optional_float(payload.get("volume1wk")),
        volume_1mo_usd=_optional_float(payload.get("volume1mo")),
        liquidity_usd=_optional_float(payload.get("liquidity")),
        last_trade_price=_optional_float(payload.get("lastTradePrice")),
        crypto_asset_tag=_infer_crypto_asset(payload),
    )


def project_gamma_market_payloads(
    payloads: Iterable[dict[str, Any]],
    *,
    fetched_at: datetime,
) -> list[CryptoMarketRow]:
    rows: list[CryptoMarketRow] = []
    for p in payloads:
        try:
            rows.append(project_gamma_market_payload(p, fetched_at=fetched_at))
        except ValueError:
            # Skip malformed market entries rather than aborting the batch.
            continue
    return rows


async def fetch_crypto_markets(
    *,
    limit: int = 500,
    active: bool = True,
    closed: bool = False,
    tag_id: int = GAMMA_CRYPTO_TAG_ID,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.get(
            GAMMA_MARKETS_URL,
            params={
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": limit,
                "order": "volume",
                "ascending": "false",
                "tag_id": tag_id,
            },
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            await http.aclose()

    if not isinstance(payload, list):
        raise TypeError(f"gamma_markets_unexpected_payload:{type(payload)!r}")
    return [m for m in payload if isinstance(m, dict)]


def _extract_yes_no_tokens(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    raw = payload.get("clobTokenIds")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(raw, list) or len(raw) < 2:
        return None, None
    return _to_optional_str(raw[0]), _to_optional_str(raw[1])


def _event_id_from_market(payload: dict[str, Any]) -> str | None:
    events = payload.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        eid = events[0].get("id")
        if eid is not None:
            return str(eid)
    return None


def _event_time_ns(payload: dict[str, Any], *, fallback: datetime) -> int:
    for key in ("updatedAt", "createdAt"):
        ns = _iso_to_ns(payload.get(key))
        if ns is not None:
            return ns
    return int(fallback.timestamp() * 1_000_000_000)


def _iso_to_ns(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return int(dt.timestamp() * 1_000_000_000)


_CRYPTO_ASSET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth", "ether"),
    "SOL": ("solana", "sol"),
    "XRP": ("xrp", "ripple"),
}


def _infer_crypto_asset(payload: dict[str, Any]) -> str | None:
    haystack_parts = [
        str(payload.get("question", "")),
        str(payload.get("slug", "")),
    ]
    haystack = " ".join(haystack_parts).lower()
    for asset, keywords in _CRYPTO_ASSET_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return asset
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    return stripped or None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


TABLE = POLYMARKET_CRYPTO_MARKETS
