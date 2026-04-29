from __future__ import annotations

import json
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from joint_research.cli import app
from joint_research.ingest.polymarket_wallet_flow import (
    WalletFlowFetchPayload,
    WalletFlowFetchRequest,
    WalletFlowIngestResult,
    WalletFlowMarketRef,
    aggregate_market_flow_hourly,
    ingest_polymarket_wallet_flow,
    load_crypto_market_refs,
    project_wallet_activity_flow,
)
from joint_research.warehouse import (
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_WALLET_FLOW,
    ParquetWriter,
    WarehousePaths,
    register_views,
)

HOUR_NS = 3_600_000_000_000


def _market_refs() -> dict[str, tuple[str, str, str]]:
    return {
        "cond-btc": ("m-btc", "BTC", "tok-btc"),
        "cond-eth": ("m-eth", "ETH", "tok-eth"),
    }


def _by_condition() -> dict[str, WalletFlowMarketRef]:
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


def _by_token() -> dict[str, WalletFlowMarketRef]:
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


def _seed_crypto_markets(paths: WarehousePaths) -> None:
    writer = ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths)
    writer.write(
        [
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m1",
                "payload_json": json.dumps({"id": "m1"}),
                "market_id": "m1",
                "condition_id": "cond-btc-1",
                "question": "q",
                "slug": "btc-1",
                "event_id": "e1",
                "yes_token_id": "tok-btc-1",
                "no_token_id": "tok-no-1",
                "active": True,
                "closed": False,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 1200.0,
                "volume_24h_usd": 100.0,
                "volume_1wk_usd": 700.0,
                "volume_1mo_usd": 1000.0,
                "liquidity_usd": 100.0,
                "last_trade_price": 0.5,
                "crypto_asset_tag": "BTC",
            },
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m2",
                "payload_json": json.dumps({"id": "m2"}),
                "market_id": "m2",
                "condition_id": "cond-eth-1",
                "question": "q",
                "slug": "eth-1",
                "event_id": "e2",
                "yes_token_id": "tok-eth-1",
                "no_token_id": "tok-no-2",
                "active": True,
                "closed": False,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 2500.0,
                "volume_24h_usd": 200.0,
                "volume_1wk_usd": 900.0,
                "volume_1mo_usd": 2000.0,
                "liquidity_usd": 200.0,
                "last_trade_price": 0.45,
                "crypto_asset_tag": "ETH",
            },
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m3",
                "payload_json": json.dumps({"id": "m3"}),
                "market_id": "m3",
                "condition_id": "cond-sol-1",
                "question": "q",
                "slug": "sol-1",
                "event_id": "e3",
                "yes_token_id": "tok-sol-1",
                "no_token_id": "tok-no-3",
                "active": False,
                "closed": True,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 500.0,
                "volume_24h_usd": 50.0,
                "volume_1wk_usd": 200.0,
                "volume_1mo_usd": 400.0,
                "liquidity_usd": 50.0,
                "last_trade_price": 0.42,
                "crypto_asset_tag": "SOL",
            },
        ]
    )


def test_selecting_top_crypto_markets_by_volume_and_asset_filter(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    _seed_crypto_markets(paths)

    all_refs = load_crypto_market_refs(paths=paths, limit_markets=3)
    assert [ref.market_id for ref in all_refs] == ["m2", "m1", "m3"]

    eth_refs = load_crypto_market_refs(paths=paths, limit_markets=3, asset="ETH")
    assert [ref.market_id for ref in eth_refs] == ["m2"]

    min_vol_refs = load_crypto_market_refs(paths=paths, limit_markets=3, min_volume=1500.0)
    assert [ref.market_id for ref in min_vol_refs] == ["m2"]


async def test_handling_multiple_markets_and_aggregation_output_counts(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    _seed_crypto_markets(paths)

    async def fake_fetch(request: WalletFlowFetchRequest) -> WalletFlowFetchPayload:
        assert len(request.market_refs) == 2
        return WalletFlowFetchPayload(
            source_clients=("fake.source",),
            wallet_activities=(
                {
                    "wallet_address": "0xaaa",
                    "activity_at": "2026-04-28T10:00:00Z",
                    "source_record_id": "a1",
                    "condition_id": "cond-btc-1",
                    "token_id": "tok-btc-1",
                    "side": "BUY",
                    "activity_type": "TRADE",
                    "usdc_size": "1000",
                },
                {
                    "wallet_address": "0xbbb",
                    "activity_at": "2026-04-28T10:01:00Z",
                    "source_record_id": "a2",
                    "condition_id": "cond-eth-1",
                    "token_id": "tok-eth-1",
                    "side": "SELL",
                    "activity_type": "TRADE",
                    "usdc_size": "1500",
                },
            ),
            relationship_reports=(),
        )

    result = await ingest_polymarket_wallet_flow(
        paths=paths,
        limit_markets=2,
        limit_events=100,
        fetch_payload=fake_fetch,
    )

    assert result.rows_written == 2
    assert result.trade_rows == 2
    assert result.copy_rows == 0
    assert result.markets_scanned == 2
    assert result.markets_with_rows == 2
    assert result.skipped_markets == 0


async def test_no_duplicate_payload_hashes_for_repeated_rows(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    _seed_crypto_markets(paths)

    activity = {
        "wallet_address": "0xdup",
        "activity_at": "2026-04-28T10:00:00Z",
        "source_record_id": "dup-1",
        "condition_id": "cond-btc-1",
        "token_id": "tok-btc-1",
        "side": "BUY",
        "activity_type": "TRADE",
        "usdc_size": "1000",
    }

    async def fake_fetch(_request: WalletFlowFetchRequest) -> WalletFlowFetchPayload:
        return WalletFlowFetchPayload(
            source_clients=("fake.source",),
            wallet_activities=(activity, dict(activity)),
            relationship_reports=(),
        )

    result = await ingest_polymarket_wallet_flow(
        paths=paths,
        limit_markets=2,
        limit_events=100,
        fetch_payload=fake_fetch,
    )

    assert result.rows_written == 1


async def test_graceful_no_row_market_behavior(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    _seed_crypto_markets(paths)

    async def empty_fetch(_request: WalletFlowFetchRequest) -> WalletFlowFetchPayload:
        return WalletFlowFetchPayload(
            source_clients=("fake.source",),
            wallet_activities=(),
            relationship_reports=(),
            warnings=("upstream_empty",),
        )

    result = await ingest_polymarket_wallet_flow(
        paths=paths,
        limit_markets=2,
        limit_events=200,
        fetch_payload=empty_fetch,
    )

    assert result.rows_written == 0
    assert result.markets_scanned == 2
    assert result.markets_with_rows == 0
    assert result.skipped_markets == 2
    assert "upstream_empty" in result.warnings


async def test_empty_unavailable_endpoint_behavior(tmp_path: Path) -> None:
    async def failing_fetch(_request: WalletFlowFetchRequest) -> WalletFlowFetchPayload:
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
    flow = con.execute(
        "SELECT buy_volume_usdc, sell_volume_usdc, large_trade_count FROM polymarket_market_flow_hourly"
    ).fetchall()
    copy_rows = con.execute("SELECT count(*) FROM polymarket_copy_flow_events").fetchone()

    assert trades == (1,)
    assert flow == [(2000.0, 0.0, 1)]
    assert copy_rows == (1,)


def test_cli_registration_for_polymarket_wallet_flow(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(
        *,
        paths,
        limit_markets,
        limit_events,
        min_volume,
        asset,
        lookback_hours,
        large_trade_usdc,
        include_copy_signals,
        fetch_payload=None,
    ):  # type: ignore[no-untyped-def]
        del (
            paths,
            limit_markets,
            limit_events,
            min_volume,
            asset,
            lookback_hours,
            large_trade_usdc,
            include_copy_signals,
            fetch_payload,
        )
        return WalletFlowIngestResult(
            rows_written=3,
            trade_rows=2,
            copy_rows=1,
            markets_scanned=10,
            markets_with_rows=4,
            skipped_markets=6,
            source_clients=("polymarket_arb.services.WalletBackfillService",),
            warnings=("demo_warning",),
            shard_path="/tmp/fake.parquet",
        )

    monkeypatch.setattr(
        "joint_research.ingest.polymarket_wallet_flow.ingest_polymarket_wallet_flow",
        fake_run,
    )
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
            "--min-volume",
            "1000",
            "--asset",
            "BTC",
            "--lookback-hours",
            "24",
            "--warehouse-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "markets_scanned=10" in result.stdout
    assert "markets_with_rows=4" in result.stdout
    assert "rows_written=3" in result.stdout
    assert "trade_rows=2" in result.stdout
    assert "copy_rows=1" in result.stdout
    assert "demo_warning" in result.stdout
