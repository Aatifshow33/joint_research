"""Ingest Polymarket whale wallet activity into the warehouse.

Reuses ``polymarket_arb.services.wallet_backfill_service.WalletBackfillService``
to discover top wallets and pull their activity, then projects each
``NormalizedWalletActivity`` into a warehouse row.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from joint_research.warehouse.schema import POLYMARKET_WALLET_ACTIVITY

WALLET_ACTIVITY_SOURCE = "data_api.activity"


@dataclass(frozen=True)
class WalletActivityRow:
    wallet_address: str
    event_time_ns: int
    payload_hash: str
    payload_json: str
    activity_type: str | None
    transaction_hash: str | None
    condition_id: str | None
    market_slug: str | None
    event_slug: str | None
    title: str | None
    token_id: str | None
    side: str | None
    outcome: str | None
    outcome_index: int | None
    size_base: float | None
    size_usdc: float | None
    price: float | None
    source_record_id: str | None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": WALLET_ACTIVITY_SOURCE,
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "wallet_address": self.wallet_address,
            "activity_type": self.activity_type,
            "transaction_hash": self.transaction_hash,
            "condition_id": self.condition_id,
            "market_slug": self.market_slug,
            "event_slug": self.event_slug,
            "title": self.title,
            "token_id": self.token_id,
            "side": self.side,
            "outcome": self.outcome,
            "outcome_index": self.outcome_index,
            "size_base": self.size_base,
            "size_usdc": self.size_usdc,
            "price": self.price,
            "source_record_id": self.source_record_id,
        }


def project_wallet_activity_dump(record: dict[str, Any]) -> WalletActivityRow:
    """Project a ``NormalizedWalletActivity.model_dump(mode='json')`` row.

    We accept the JSON-serialized form directly so this function can be unit
    tested without depending on the polymarket-arb pydantic models.
    """

    wallet_address = record.get("wallet_address")
    if not isinstance(wallet_address, str) or not wallet_address:
        raise ValueError("wallet_activity_missing_address")

    activity_at = record.get("activity_at")
    fetched_at = record.get("fetched_at")
    event_time_ns = _ns_from_iso(activity_at) or _ns_from_iso(fetched_at)
    if event_time_ns is None:
        raise ValueError("wallet_activity_missing_timestamp")

    source_record_id = record.get("source_record_id")
    payload_json = json.dumps(record, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(
        f"{wallet_address}|{source_record_id or payload_json}".encode("utf-8")
    ).hexdigest()

    return WalletActivityRow(
        wallet_address=wallet_address.lower(),
        event_time_ns=event_time_ns,
        payload_hash=digest,
        payload_json=payload_json,
        activity_type=_optional_str(record.get("activity_type")),
        transaction_hash=_optional_str(record.get("transaction_hash")),
        condition_id=_optional_str(record.get("condition_id")),
        market_slug=_optional_str(record.get("market_slug")),
        event_slug=_optional_str(record.get("event_slug")),
        title=_optional_str(record.get("title")),
        token_id=_optional_str(record.get("token_id")),
        side=_optional_str(record.get("side")),
        outcome=_optional_str(record.get("outcome")),
        outcome_index=_optional_int(record.get("outcome_index")),
        size_base=_optional_float(record.get("size")),
        size_usdc=_optional_float(record.get("usdc_size")),
        price=_optional_float(record.get("price")),
        source_record_id=_optional_str(source_record_id),
    )


def _ns_from_iso(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        from datetime import datetime  # noqa: PLC0415
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


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


TABLE = POLYMARKET_WALLET_ACTIVITY
