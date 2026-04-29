from __future__ import annotations

from pathlib import Path

import duckdb
from typer.testing import CliRunner

from joint_research.cli import app
from joint_research.ingest.polymarket_wallet_flow import (
    WalletFlowFetchPayload,
    WalletFlowIngestResult,
    WalletFlowMarketRef,
    aggregate_market_flow_hourly,
    ingest_polymarket_wallet_flow,
    project_wallet_activity_flow,
)
from joint_research.warehouse import POLYMARKET_WALLET_FLOW, ParquetWriter, WarehousePaths, register_views

HOUR_NS = 3_600_000_000_000


def _market_refs():
    return {
        "cond-btc": ("m-btc", "BTC", "tok-btc"),
        "cond-eth": ("m-eth", "ETH", "tok-eth"),
    }


def _by_condition():
    refs: dict[str, WalletFlowMarketRef] = {}
    for condition_id, (market_id, asset, token_id) in _market_refs().items():
        refs[condition_id] = WalletFlowMarketRef(
            market_id=market_id,
            condition_id=condition_id,
            token_id=token_id,
            asset=asset,
            market_slug=market_id,
        )
    return refs


def _by_token():
    refs: dict[str, WalletFlowMarketRef] = {}
    for condition_id, (market_id, asset, token_id) in _market_refs().items():
        refs[token_id] = WalletFlowMarketRef(
            market_id=market_id,
            condition_id=condition_id,
            token_id=token_id,
            asset=asset,
            market_slug=market_id,
        )
    return refs


def test_payload_projection_into_schema_and_hash_stability() -> None:
    record = {
        "wallet_address": "0xABC",
        "activity_at": "2026-04-28T10:00:00Z",
        "source_record_id": "data_api.activity:tx1",
        "condition_id": "cond-btc",
        "token_id": "tok-btc",
        "side": "BUY",
        "activity_type": "TRADE",
        "size": "2.0",
        "usdc_size": "1200.0",
        "price": "0.6",
    }
    row_a = project_wallet_activity_flow(
        record,
        market_refs_by_condition=_by_condition(),
        market_refs_by_token=_by_token(),
        large_trade_usdc=1_000.0,
    )
    row_b = project_wallet_activity_flow(
        dict(reversed(list(record.items()))),
        market_refs_by_condition=_by_condition(),
        market_refs_by_token=_by_token(),
        large_trade_usdc=1_000.0,
    )

    assert row_a is not None
    assert row_b is not None
    assert row_a.record_type == "wallet_trade"
    assert row_a.market_id == "m-btc"
    assert row_a.asset == "BTC"
    assert row_a.notional_usdc == 1200.0
    assert row_a.payload_hash == row_b.payload_hash
    warehouse_row = row_a.to_warehouse_row()
    assert warehouse_row["record_type"] == "wallet_trade"
    assert warehouse_row["source_record_id"] == "data_api.activity:tx1"


def test_flow_aggregate_calculation_and_whale_threshold_behavior() -> None:
    base = {
        "wallet_address": "0xabc",
        "activity_type": "TRADE",
        "condition_id": "cond-btc",
        "token_id": "tok-btc",
        "price": "0.5",
    }
    records = [
        dict(base, source_record_id="a1", activity_at="2026-04-28T10:05:00Z", side="BUY", usdc_size="2000"),
        dict(base, source_record_id="a2", activity_at="2026-04-28T10:10:00Z", side="SELL", usdc_size="500"),
        dict(base, source_record_id="a3", activity_at="2026-04-28T10:20:00Z", side="BUY", usdc_size="300"),
    ]
    rows = [
        project_wallet_activity_flow(
            record,
            market_refs_by_condition=_by_condition(),
            market_refs_by_token=_by_token(),
            large_trade_usdc=1_000.0,
        )
        for record in records
    ]
    typed_rows = [row for row in rows if row is not None]
    assert typed_rows[0].is_large_trade is True
    assert typed_rows[1].is_large_trade is False

    aggregates = aggregate_market_flow_hourly(typed_rows)
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.buy_volume_usdc == 2300.0
    assert agg.sell_volume_usdc == 500.0
    assert agg.net_flow_usdc == 1800.0
    assert agg.large_trade_count == 1
    assert agg.whale_flow_score > 0


async def test_empty_unavailable_endpoint_behavior(tmp_path: Path) -> None:
    async def failing_fetch(_limit_events: int, _include_copy: bool) -> WalletFlowFetchPayload:
        raise RuntimeError("upstream_unavailable")

    result = await ingest_polymarket_wallet_flow(
        paths=WarehousePaths(root=tmp_path),
        limit_markets=5,
        limit_events=200,
        fetch_payload=failing_fetch,
    )

    assert result.rows_written == 0
    assert result.shard_path == ""
    assert any("wallet_flow_fetch_failed" in warning for warning in result.warnings)


def test_view_registration_for_wallet_flow(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_WALLET_FLOW, paths=paths)
    writer.write(
        [
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "h1",
                "payload_json": "{}",
                "record_type": "wallet_trade",
                "source_record_id": "trade-1",
                "wallet_address": "0xabc",
                "leader_wallet": None,
                "follower_wallet": None,
                "market_id": "m-btc",
                "condition_id": "cond-btc",
                "token_id": "tok-btc",
                "asset": "BTC",
                "side": "BUY",
                "action": "TRADE",
                "size_base": 1.0,
                "notional_usdc": 2000.0,
                "price_probability": 0.55,
                "flow_sign": 1,
                "is_large_trade": True,
                "lag_seconds": None,
                "relationship_confidence": None,
                "relationship_status": None,
            },
            {
                "event_time_ns": 10 * HOUR_NS + 100,
                "source": "test",
                "payload_hash": "h2",
                "payload_json": "{}",
                "record_type": "copy_event",
                "source_record_id": "copy-1",
                "wallet_address": "0xfollower",
                "leader_wallet": "0xleader",
                "follower_wallet": "0xfollower",
                "market_id": "m-btc",
                "condition_id": "cond-btc",
                "token_id": "tok-btc",
                "asset": "BTC",
                "side": "BUY",
                "action": "copy_follow",
                "size_base": None,
                "notional_usdc": None,
                "price_probability": None,
                "flow_sign": 1,
                "is_large_trade": None,
                "lag_seconds": 120,
                "relationship_confidence": 0.8,
                "relationship_status": "accepted",
            },
        ]
    )

    con = duckdb.connect()
    register_views(con, paths)

    trades = con.execute("SELECT count(*) FROM polymarket_wallet_trades").fetchone()
    flow = con.execute("SELECT buy_volume_usdc, sell_volume_usdc, large_trade_count FROM polymarket_market_flow_hourly").fetchall()
    copy_rows = con.execute("SELECT count(*) FROM polymarket_copy_flow_events").fetchone()

    assert trades == (1,)
    assert flow == [(2000.0, 0.0, 1)]
    assert copy_rows == (1,)


def test_cli_registration_for_polymarket_wallet_flow(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(*, paths, limit_markets, limit_events, large_trade_usdc, include_copy_signals, fetch_payload=None):  # type: ignore[no-untyped-def]
        del paths, limit_markets, limit_events, large_trade_usdc, include_copy_signals, fetch_payload
        return WalletFlowIngestResult(
            rows_written=3,
            trade_rows=2,
            copy_rows=1,
            source_clients=("polymarket_arb.services.WalletBackfillService",),
            warnings=("demo_warning",),
            shard_path="/tmp/fake.parquet",
        )

    monkeypatch.setattr("joint_research.ingest.polymarket_wallet_flow.ingest_polymarket_wallet_flow", fake_run)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "polymarket-wallet-flow",
            "--limit-markets",
            "5",
            "--limit-events",
            "200",
            "--warehouse-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "rows_written=3" in result.stdout
    assert "trade_rows=2" in result.stdout
    assert "copy_rows=1" in result.stdout
    assert "demo_warning" in result.stdout
