"""Polymarket wallet/trader-flow ingestion (public/no-auth, paper-only)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import duckdb

from joint_research.warehouse import POLYMARKET_WALLET_FLOW, WarehousePaths, register_views
from joint_research.warehouse.writer import ParquetWriter

WALLET_FLOW_TRADE_SOURCE = "polymarket_arb.wallet_backfill.activity"
WALLET_FLOW_COPY_SOURCE = "polymarket_arb.relationship_engine.copy_event"
HOUR_NS = 3_600_000_000_000


@dataclass(frozen=True)
class WalletFlowMarketRef:
    market_id: str
    condition_id: str | None
    token_id: str | None
    asset: str
    market_slug: str | None


@dataclass(frozen=True)
class WalletFlowRow:
    event_time_ns: int
    payload_hash: str
    payload_json: str
    source: str
    record_type: str
    source_record_id: str
    wallet_address: str | None
    leader_wallet: str | None
    follower_wallet: str | None
    market_id: str | None
    condition_id: str | None
    token_id: str | None
    asset: str | None
    side: str | None
    action: str | None
    size_base: float | None
    notional_usdc: float | None
    price_probability: float | None
    flow_sign: int | None
    is_large_trade: bool | None
    lag_seconds: int | None
    relationship_confidence: float | None
    relationship_status: str | None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": self.source,
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "record_type": self.record_type,
            "source_record_id": self.source_record_id,
            "wallet_address": self.wallet_address,
            "leader_wallet": self.leader_wallet,
            "follower_wallet": self.follower_wallet,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "token_id": self.token_id,
            "asset": self.asset,
            "side": self.side,
            "action": self.action,
            "size_base": self.size_base,
            "notional_usdc": self.notional_usdc,
            "price_probability": self.price_probability,
            "flow_sign": self.flow_sign,
            "is_large_trade": self.is_large_trade,
            "lag_seconds": self.lag_seconds,
            "relationship_confidence": self.relationship_confidence,
            "relationship_status": self.relationship_status,
        }


@dataclass(frozen=True)
class WalletFlowFetchPayload:
    source_clients: tuple[str, ...]
    wallet_activities: tuple[dict[str, Any], ...]
    relationship_reports: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class WalletFlowIngestResult:
    rows_written: int
    trade_rows: int
    copy_rows: int
    source_clients: tuple[str, ...]
    warnings: tuple[str, ...]
    shard_path: str


@dataclass(frozen=True)
class WalletFlowHourlyAggregate:
    market_id: str | None
    token_id: str | None
    asset: str | None
    hour_open_time_ns: int
    buy_volume_usdc: float
    sell_volume_usdc: float
    net_flow_usdc: float
    unique_active_wallets: int
    large_trade_count: int
    whale_flow_score: float


async def ingest_polymarket_wallet_flow(
    *,
    paths: WarehousePaths,
    limit_markets: int = 20,
    limit_events: int = 500,
    large_trade_usdc: float = 1_000.0,
    include_copy_signals: bool = True,
    fetch_payload: Callable[[int, bool], Awaitable[WalletFlowFetchPayload]] | None = None,
) -> WalletFlowIngestResult:
    market_refs = load_crypto_market_refs(paths=paths, limit_markets=limit_markets)
    by_condition: dict[str, WalletFlowMarketRef] = {
        ref.condition_id: ref for ref in market_refs if ref.condition_id
    }
    by_token: dict[str, WalletFlowMarketRef] = {
        ref.token_id: ref for ref in market_refs if ref.token_id
    }

    warnings: list[str] = []
    payload: WalletFlowFetchPayload | None = None
    fetcher = fetch_payload or _fetch_wallet_flow_payload_from_polymarket_arb
    try:
        payload = await fetcher(limit_events, include_copy_signals)
    except Exception as exc:  # noqa: BLE001 - graceful empty behavior by contract
        warnings.append(f"wallet_flow_fetch_failed:{type(exc).__name__}:{exc}")
        payload = WalletFlowFetchPayload(
            source_clients=("polymarket_arb",),
            wallet_activities=(),
            relationship_reports=(),
        )

    rows: list[WalletFlowRow] = []
    for record in payload.wallet_activities:
        row = project_wallet_activity_flow(
            record,
            market_refs_by_condition=by_condition,
            market_refs_by_token=by_token,
            large_trade_usdc=large_trade_usdc,
        )
        if row is not None:
            rows.append(row)

    if include_copy_signals:
        for report in payload.relationship_reports:
            rows.extend(
                project_copy_relationship_report(
                    report,
                    market_refs_by_condition=by_condition,
                    market_refs_by_token=by_token,
                )
            )

    rows.sort(key=lambda row: row.event_time_ns, reverse=True)
    rows = rows[: max(limit_events, 0)]

    if not rows:
        warnings.append("wallet_flow_no_rows_after_projection")
        return WalletFlowIngestResult(
            rows_written=0,
            trade_rows=0,
            copy_rows=0,
            source_clients=payload.source_clients,
            warnings=tuple(warnings),
            shard_path="",
        )

    writer = ParquetWriter(table=POLYMARKET_WALLET_FLOW, paths=paths)
    shard = writer.write([row.to_warehouse_row() for row in rows])
    trade_rows = sum(1 for row in rows if row.record_type == "wallet_trade")
    copy_rows = sum(1 for row in rows if row.record_type == "copy_event")
    return WalletFlowIngestResult(
        rows_written=len(rows),
        trade_rows=trade_rows,
        copy_rows=copy_rows,
        source_clients=payload.source_clients,
        warnings=tuple(warnings),
        shard_path=str(shard),
    )


def load_crypto_market_refs(*, paths: WarehousePaths, limit_markets: int) -> list[WalletFlowMarketRef]:
    con = duckdb.connect()
    register_views(con, paths)
    rows = con.execute(
        """
        WITH latest AS (
          SELECT * EXCLUDE (rn)
          FROM (
            SELECT
              market_id,
              condition_id,
              yes_token_id AS token_id,
              crypto_asset_tag AS asset,
              slug AS market_slug,
              volume_1mo_usd,
              event_time_ns,
              ROW_NUMBER() OVER (
                PARTITION BY market_id
                ORDER BY event_time_ns DESC, ingest_time_ns DESC
              ) AS rn
            FROM polymarket_crypto_markets
            WHERE market_id IS NOT NULL
              AND crypto_asset_tag IS NOT NULL
          )
          WHERE rn = 1
        )
        SELECT market_id, condition_id, token_id, upper(asset), market_slug
        FROM latest
        ORDER BY coalesce(volume_1mo_usd, 0) DESC, market_id
        LIMIT ?
        """,
        [max(limit_markets, 0)],
    ).fetchall()
    return [
        WalletFlowMarketRef(
            market_id=str(row[0]),
            condition_id=str(row[1]) if row[1] is not None else None,
            token_id=str(row[2]) if row[2] is not None else None,
            asset=str(row[3]).upper(),
            market_slug=row[4],
        )
        for row in rows
    ]


def project_wallet_activity_flow(
    record: dict[str, Any],
    *,
    market_refs_by_condition: dict[str, WalletFlowMarketRef],
    market_refs_by_token: dict[str, WalletFlowMarketRef],
    large_trade_usdc: float,
) -> WalletFlowRow | None:
    condition_id = _optional_str(record.get("condition_id"))
    token_id = _optional_str(record.get("token_id"))
    ref = _find_market_ref(
        condition_id=condition_id,
        token_id=token_id,
        market_refs_by_condition=market_refs_by_condition,
        market_refs_by_token=market_refs_by_token,
    )
    if ref is None:
        return None

    wallet_address = _normalize_wallet(record.get("wallet_address"))
    if wallet_address is None:
        return None
    event_time_ns = _ns_from_iso(record.get("activity_at")) or _ns_from_iso(record.get("fetched_at"))
    if event_time_ns is None:
        return None

    side = _optional_str(record.get("side"))
    action = _optional_str(record.get("activity_type"))
    size_base = _optional_float(record.get("size"))
    notional_usdc = _optional_float(record.get("usdc_size"))
    price_probability = _optional_float(record.get("price"))
    if notional_usdc is None and size_base is not None and price_probability is not None:
        notional_usdc = size_base * price_probability
    flow_sign = _flow_sign_from_side(side)
    is_large_trade = (
        abs(notional_usdc) >= large_trade_usdc if notional_usdc is not None else None
    )
    source_record_id = _optional_str(record.get("source_record_id")) or (
        f"wallet_trade:{wallet_address}:{event_time_ns}:{condition_id or token_id or 'na'}"
    )
    payload_json = _canonical_json(record)
    payload_hash = _payload_hash(
        record_type="wallet_trade",
        source_record_id=source_record_id,
        payload_json=payload_json,
    )
    return WalletFlowRow(
        event_time_ns=event_time_ns,
        payload_hash=payload_hash,
        payload_json=payload_json,
        source=WALLET_FLOW_TRADE_SOURCE,
        record_type="wallet_trade",
        source_record_id=source_record_id,
        wallet_address=wallet_address,
        leader_wallet=None,
        follower_wallet=None,
        market_id=ref.market_id,
        condition_id=condition_id or ref.condition_id,
        token_id=token_id or ref.token_id,
        asset=ref.asset,
        side=side,
        action=action,
        size_base=size_base,
        notional_usdc=notional_usdc,
        price_probability=price_probability,
        flow_sign=flow_sign,
        is_large_trade=is_large_trade,
        lag_seconds=None,
        relationship_confidence=None,
        relationship_status=None,
    )


def project_copy_relationship_report(
    report: dict[str, Any],
    *,
    market_refs_by_condition: dict[str, WalletFlowMarketRef],
    market_refs_by_token: dict[str, WalletFlowMarketRef],
) -> list[WalletFlowRow]:
    rows: list[WalletFlowRow] = []
    leader_wallet = _normalize_wallet(report.get("leader_wallet"))
    follower_wallet = _normalize_wallet(report.get("follower_wallet"))
    confidence = _optional_float(report.get("confidence_score"))
    status = _optional_str(report.get("status"))
    for evidence in report.get("evidence", []):
        if not isinstance(evidence, dict):
            continue
        condition_id = _optional_str(evidence.get("condition_id"))
        token_id = _optional_str(evidence.get("token_id"))
        ref = _find_market_ref(
            condition_id=condition_id,
            token_id=token_id,
            market_refs_by_condition=market_refs_by_condition,
            market_refs_by_token=market_refs_by_token,
        )
        if ref is None:
            continue
        event_time_ns = _ns_from_iso(evidence.get("follower_activity_at")) or _ns_from_iso(
            evidence.get("leader_activity_at")
        )
        if event_time_ns is None:
            continue
        side = _optional_str(evidence.get("side"))
        lag_seconds = _optional_int(evidence.get("lag_seconds"))
        source_record_id = (
            f"copy_event:{_optional_str(evidence.get('leader_activity_id')) or 'na'}:"
            f"{_optional_str(evidence.get('follower_activity_id')) or 'na'}:"
            f"{ref.market_id}:{event_time_ns}"
        )
        payload_json = _canonical_json({"report": report, "evidence": evidence})
        rows.append(
            WalletFlowRow(
                event_time_ns=event_time_ns,
                payload_hash=_payload_hash(
                    record_type="copy_event",
                    source_record_id=source_record_id,
                    payload_json=payload_json,
                ),
                payload_json=payload_json,
                source=WALLET_FLOW_COPY_SOURCE,
                record_type="copy_event",
                source_record_id=source_record_id,
                wallet_address=follower_wallet,
                leader_wallet=leader_wallet,
                follower_wallet=follower_wallet,
                market_id=ref.market_id,
                condition_id=condition_id or ref.condition_id,
                token_id=token_id or ref.token_id,
                asset=ref.asset,
                side=side,
                action="copy_follow",
                size_base=None,
                notional_usdc=None,
                price_probability=None,
                flow_sign=_flow_sign_from_side(side),
                is_large_trade=None,
                lag_seconds=lag_seconds,
                relationship_confidence=confidence,
                relationship_status=status,
            )
        )
    return rows


def aggregate_market_flow_hourly(rows: Iterable[WalletFlowRow]) -> list[WalletFlowHourlyAggregate]:
    grouped: dict[tuple[str | None, str | None, str | None, int], dict[str, object]] = defaultdict(
        lambda: {
            "buy_volume_usdc": 0.0,
            "sell_volume_usdc": 0.0,
            "net_flow_usdc": 0.0,
            "wallets": set(),
            "large_trade_count": 0,
        }
    )
    for row in rows:
        if row.record_type != "wallet_trade":
            continue
        hour_open_time_ns = row.event_time_ns - (row.event_time_ns % HOUR_NS)
        key = (row.market_id, row.token_id, row.asset, hour_open_time_ns)
        bucket = grouped[key]
        notional = abs(row.notional_usdc) if row.notional_usdc is not None else 0.0
        if row.flow_sign and row.flow_sign > 0:
            bucket["buy_volume_usdc"] = float(bucket["buy_volume_usdc"]) + notional
        elif row.flow_sign and row.flow_sign < 0:
            bucket["sell_volume_usdc"] = float(bucket["sell_volume_usdc"]) + notional
        bucket["net_flow_usdc"] = float(bucket["net_flow_usdc"]) + (
            float(row.flow_sign) * notional if row.flow_sign is not None else 0.0
        )
        if row.wallet_address:
            wallets = bucket["wallets"]
            assert isinstance(wallets, set)
            wallets.add(row.wallet_address)
        if row.is_large_trade:
            bucket["large_trade_count"] = int(bucket["large_trade_count"]) + 1

    aggregates: list[WalletFlowHourlyAggregate] = []
    for (market_id, token_id, asset, hour_open_time_ns), bucket in grouped.items():
        buy_volume = float(bucket["buy_volume_usdc"])
        sell_volume = float(bucket["sell_volume_usdc"])
        total_volume = buy_volume + sell_volume
        net_flow = float(bucket["net_flow_usdc"])
        wallets = bucket["wallets"]
        assert isinstance(wallets, set)
        large_trade_count = int(bucket["large_trade_count"])
        whale_score = 0.0
        if total_volume > 0:
            whale_score = (net_flow / total_volume) * math_log1p(large_trade_count)
        aggregates.append(
            WalletFlowHourlyAggregate(
                market_id=market_id,
                token_id=token_id,
                asset=asset,
                hour_open_time_ns=hour_open_time_ns,
                buy_volume_usdc=buy_volume,
                sell_volume_usdc=sell_volume,
                net_flow_usdc=net_flow,
                unique_active_wallets=len(wallets),
                large_trade_count=large_trade_count,
                whale_flow_score=whale_score,
            )
        )
    aggregates.sort(
        key=lambda row: (
            row.asset or "",
            row.market_id or "",
            row.token_id or "",
            row.hour_open_time_ns,
        )
    )
    return aggregates


async def _fetch_wallet_flow_payload_from_polymarket_arb(
    limit_events: int,
    include_copy_signals: bool,
) -> WalletFlowFetchPayload:
    from polymarket_arb.config import Settings  # noqa: PLC0415
    from polymarket_arb.relationships.engine import RelationshipEngine  # noqa: PLC0415
    from polymarket_arb.services.wallet_backfill_service import (  # noqa: PLC0415
        WalletBackfillService,
    )

    settings = Settings()
    service = WalletBackfillService(settings=settings)
    wallet_limit = max(5, min(limit_events, 50))
    _selected, _seeds, activities = await service.collect_wallet_backfill(limit=wallet_limit)
    activity_payloads = tuple(activity.model_dump(mode="json") for activity in activities)

    relationship_reports: tuple[dict[str, Any], ...] = ()
    if include_copy_signals:
        reports = RelationshipEngine().build_relationship_reports(activities=activities)
        relationship_reports = tuple(report.to_output() for report in reports)

    return WalletFlowFetchPayload(
        source_clients=(
            "polymarket_arb.services.WalletBackfillService",
            "polymarket_arb.relationships.RelationshipEngine",
        ),
        wallet_activities=activity_payloads,
        relationship_reports=relationship_reports,
    )


def _find_market_ref(
    *,
    condition_id: str | None,
    token_id: str | None,
    market_refs_by_condition: dict[str, WalletFlowMarketRef],
    market_refs_by_token: dict[str, WalletFlowMarketRef],
) -> WalletFlowMarketRef | None:
    if condition_id and condition_id in market_refs_by_condition:
        return market_refs_by_condition[condition_id]
    if token_id and token_id in market_refs_by_token:
        return market_refs_by_token[token_id]
    return None


def _flow_sign_from_side(side: str | None) -> int | None:
    if side is None:
        return None
    normalized = side.strip().lower()
    if normalized in {"buy", "bid"}:
        return 1
    if normalized in {"sell", "ask"}:
        return -1
    return 0


def _ns_from_iso(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1_000_000_000)


def _normalize_wallet(value: Any) -> str | None:
    wallet = _optional_str(value)
    return wallet.lower() if wallet is not None else None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(*, record_type: str, source_record_id: str, payload_json: str) -> str:
    return hashlib.sha256(
        f"{record_type}|{source_record_id}|{payload_json}".encode("utf-8")
    ).hexdigest()


def math_log1p(value: int) -> float:
    import math  # noqa: PLC0415

    return math.log1p(max(value, 0))


TABLE = POLYMARKET_WALLET_FLOW
