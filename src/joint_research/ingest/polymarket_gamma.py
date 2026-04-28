"""Ingest Polymarket Gamma /events payloads into the warehouse.

The Gamma API returns event objects with arbitrary nested structure. We keep
the raw JSON in ``payload_json`` and project the columns we actually want to
filter/join on into typed schema fields.

The projection is kept defensive: every field is optional except ``event_id``,
because Polymarket has a long history of changing field shapes mid-season.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from joint_research.warehouse.schema import POLYMARKET_GAMMA_EVENTS

GAMMA_SOURCE = "gamma.events"


@dataclass(frozen=True)
class GammaEventRow:
    """One row written to ``polymarket_gamma_events``."""

    event_id: str
    event_time_ns: int
    payload_json: str
    payload_hash: str
    slug: str | None
    title: str | None
    category: str | None
    active: bool | None
    closed: bool | None
    archived: bool | None
    start_date_iso: str | None
    end_date_iso: str | None
    volume_usd: float | None
    liquidity_usd: float | None
    market_count: int | None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": GAMMA_SOURCE,
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "event_id": self.event_id,
            "slug": self.slug,
            "title": self.title,
            "category": self.category,
            "active": self.active,
            "closed": self.closed,
            "archived": self.archived,
            "start_date_iso": self.start_date_iso,
            "end_date_iso": self.end_date_iso,
            "volume_usd": self.volume_usd,
            "liquidity_usd": self.liquidity_usd,
            "market_count": self.market_count,
        }


def project_gamma_event_payload(
    payload: dict[str, Any],
    *,
    fetched_at: datetime,
) -> GammaEventRow:
    event_id = payload.get("id")
    if event_id is None:
        raise ValueError("gamma_event_missing_id")
    event_id_str = str(event_id)

    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = canonical_payload_hash(payload_json)

    event_time_ns = _event_time_ns_from_payload(payload, fallback=fetched_at)

    return GammaEventRow(
        event_id=event_id_str,
        event_time_ns=event_time_ns,
        payload_json=payload_json,
        payload_hash=payload_hash,
        slug=_optional_str(payload.get("slug")),
        title=_optional_str(payload.get("title")),
        category=_optional_str(payload.get("category")),
        active=_optional_bool(payload.get("active")),
        closed=_optional_bool(payload.get("closed")),
        archived=_optional_bool(payload.get("archived")),
        start_date_iso=_optional_str(payload.get("startDate")),
        end_date_iso=_optional_str(payload.get("endDate")),
        volume_usd=_optional_float(payload.get("volume")),
        liquidity_usd=_optional_float(payload.get("liquidity")),
        market_count=_optional_int_from_markets(payload.get("markets")),
    )


def project_gamma_event_payloads(
    payloads: Iterable[dict[str, Any]],
    *,
    fetched_at: datetime,
) -> list[GammaEventRow]:
    return [project_gamma_event_payload(p, fetched_at=fetched_at) for p in payloads]


def canonical_payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _event_time_ns_from_payload(payload: dict[str, Any], *, fallback: datetime) -> int:
    """Pick the most recent meaningful timestamp on the event payload.

    Gamma events ship a few candidate fields. We prefer ``updatedAt`` (most
    recent state change), fall back to ``createdAt``, and finally to the wall
    clock at fetch time so we never lose a row to a malformed timestamp.
    """

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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    return stripped or None


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


def _optional_int_from_markets(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


# Re-export for symmetry with the table this ingestor populates.
TABLE = POLYMARKET_GAMMA_EVENTS
