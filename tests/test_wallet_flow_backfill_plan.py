from __future__ import annotations

from pathlib import Path

from joint_research.ingest.polymarket_wallet_flow import WalletFlowIngestResult
from joint_research.ingest.wallet_flow_backfill_plan import (
    STAGE_1_QUICK,
    STAGE_2_DEPTH,
    STAGE_3_BREADTH,
    MarketCoverageRow,
    build_backfill_plan,
    load_market_coverage,
    run_wallet_flow_backfill_plan,
)
from joint_research.warehouse import (
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_WALLET_FLOW,
    ParquetWriter,
    WarehousePaths,
)

HOUR_NS = 3_600_000_000_000


def _seed_crypto_markets(paths: WarehousePaths) -> None:
    writer = ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths)
    writer.write(
        [
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m-btc",
                "payload_json": "{}",
                "market_id": "m-btc",
                "condition_id": "cond-btc",
                "question": "btc",
                "slug": "btc-market",
                "event_id": "e-btc",
                "yes_token_id": "tok-btc",
                "no_token_id": "tok-no-btc",
                "active": True,
                "closed": False,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 90_000.0,
                "volume_24h_usd": 6_000.0,
                "volume_1wk_usd": 20_000.0,
                "volume_1mo_usd": 80_000.0,
                "liquidity_usd": 7_500.0,
                "last_trade_price": 0.55,
                "crypto_asset_tag": "BTC",
            },
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m-eth",
                "payload_json": "{}",
                "market_id": "m-eth",
                "condition_id": "cond-eth",
                "question": "eth",
                "slug": "eth-market",
                "event_id": "e-eth",
                "yes_token_id": "tok-eth",
                "no_token_id": "tok-no-eth",
                "active": True,
                "closed": False,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 70_000.0,
                "volume_24h_usd": 4_000.0,
                "volume_1wk_usd": 16_000.0,
                "volume_1mo_usd": 60_000.0,
                "liquidity_usd": 5_500.0,
                "last_trade_price": 0.48,
                "crypto_asset_tag": "ETH",
            },
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m-sol",
                "payload_json": "{}",
                "market_id": "m-sol",
                "condition_id": "cond-sol",
                "question": "sol",
                "slug": "sol-market",
                "event_id": "e-sol",
                "yes_token_id": "tok-sol",
                "no_token_id": "tok-no-sol",
                "active": True,
                "closed": False,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 40_000.0,
                "volume_24h_usd": 2_000.0,
                "volume_1wk_usd": 8_000.0,
                "volume_1mo_usd": 35_000.0,
                "liquidity_usd": 3_000.0,
                "last_trade_price": 0.41,
                "crypto_asset_tag": "SOL",
            },
            {
                "event_time_ns": 10 * HOUR_NS,
                "source": "test",
                "payload_hash": "m-xrp",
                "payload_json": "{}",
                "market_id": "m-xrp",
                "condition_id": "cond-xrp",
                "question": "xrp",
                "slug": "xrp-market",
                "event_id": "e-xrp",
                "yes_token_id": "tok-xrp",
                "no_token_id": "tok-no-xrp",
                "active": False,
                "closed": True,
                "archived": False,
                "end_date_iso": None,
                "volume_total_usd": 20_000.0,
                "volume_24h_usd": 1_000.0,
                "volume_1wk_usd": 3_000.0,
                "volume_1mo_usd": 15_000.0,
                "liquidity_usd": 2_000.0,
                "last_trade_price": 0.39,
                "crypto_asset_tag": "XRP",
            },
        ]
    )


def _seed_wallet_flow(paths: WarehousePaths) -> None:
    writer = ParquetWriter(table=POLYMARKET_WALLET_FLOW, paths=paths)
    writer.write(
        [
            {
                "event_time_ns": 11 * HOUR_NS,
                "source": "test",
                "payload_hash": "wf-1",
                "payload_json": "{}",
                "record_type": "wallet_trade",
                "source_record_id": "trade-1",
                "wallet_address": "0xbtc1",
                "leader_wallet": None,
                "follower_wallet": None,
                "market_id": "m-btc",
                "condition_id": "cond-btc",
                "token_id": "tok-btc",
                "asset": "BTC",
                "side": "BUY",
                "action": "TRADE",
                "size_base": 10.0,
                "notional_usdc": 1000.0,
                "price_probability": 0.5,
                "flow_sign": 1,
                "is_large_trade": True,
                "lag_seconds": None,
                "relationship_confidence": None,
                "relationship_status": None,
            },
            {
                "event_time_ns": 12 * HOUR_NS,
                "source": "test",
                "payload_hash": "wf-2",
                "payload_json": "{}",
                "record_type": "wallet_trade",
                "source_record_id": "trade-2",
                "wallet_address": "0xbtc2",
                "leader_wallet": None,
                "follower_wallet": None,
                "market_id": "m-btc",
                "condition_id": "cond-btc",
                "token_id": "tok-btc",
                "asset": "BTC",
                "side": "SELL",
                "action": "TRADE",
                "size_base": 8.0,
                "notional_usdc": 800.0,
                "price_probability": 0.45,
                "flow_sign": -1,
                "is_large_trade": False,
                "lag_seconds": None,
                "relationship_confidence": None,
                "relationship_status": None,
            },
            {
                "event_time_ns": 12 * HOUR_NS + 100,
                "source": "test",
                "payload_hash": "wf-copy-1",
                "payload_json": "{}",
                "record_type": "copy_event",
                "source_record_id": "copy-1",
                "wallet_address": "0xfollow",
                "leader_wallet": "0xlead",
                "follower_wallet": "0xfollow",
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
                "lag_seconds": 45,
                "relationship_confidence": 0.8,
                "relationship_status": "accepted",
            },
            {
                "event_time_ns": 11 * HOUR_NS,
                "source": "test",
                "payload_hash": "wf-eth-1",
                "payload_json": "{}",
                "record_type": "wallet_trade",
                "source_record_id": "trade-eth-1",
                "wallet_address": "0xeth1",
                "leader_wallet": None,
                "follower_wallet": None,
                "market_id": "m-eth",
                "condition_id": "cond-eth",
                "token_id": "tok-eth",
                "asset": "ETH",
                "side": "BUY",
                "action": "TRADE",
                "size_base": 5.0,
                "notional_usdc": 500.0,
                "price_probability": 0.52,
                "flow_sign": 1,
                "is_large_trade": False,
                "lag_seconds": None,
                "relationship_confidence": None,
                "relationship_status": None,
            },
        ]
    )


def test_coverage_calculation(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    _seed_crypto_markets(paths)
    _seed_wallet_flow(paths)

    coverage = load_market_coverage(paths=paths)
    by_market = {row.market_id: row for row in coverage}

    assert len(coverage) == 4
    assert by_market["m-btc"].wallet_flow_rows == 3
    assert by_market["m-btc"].trade_rows == 2
    assert by_market["m-btc"].copy_rows == 1
    assert by_market["m-btc"].market_flow_hourly_rows >= 1
    assert by_market["m-sol"].wallet_flow_rows == 0


def test_priority_ranking_prefers_btc_eth_high_volume_undercovered() -> None:
    rows = [
        MarketCoverageRow(
            market_id="eth-under",
            market_slug="eth-under",
            asset="ETH",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=80_000,
            volume_total_usd=100_000,
            wallet_flow_rows=0,
            trade_rows=0,
            copy_rows=0,
            market_flow_hourly_rows=0,
            whale_flow_hourly_rows=0,
        ),
        MarketCoverageRow(
            market_id="btc-covered",
            market_slug="btc-covered",
            asset="BTC",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=120_000,
            volume_total_usd=150_000,
            wallet_flow_rows=200,
            trade_rows=190,
            copy_rows=10,
            market_flow_hourly_rows=80,
            whale_flow_hourly_rows=70,
        ),
        MarketCoverageRow(
            market_id="btc-under",
            market_slug="btc-under",
            asset="BTC",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=90_000,
            volume_total_usd=90_000,
            wallet_flow_rows=0,
            trade_rows=0,
            copy_rows=0,
            market_flow_hourly_rows=0,
            whale_flow_hourly_rows=0,
        ),
        MarketCoverageRow(
            market_id="sol-under",
            market_slug="sol-under",
            asset="SOL",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=200_000,
            volume_total_usd=200_000,
            wallet_flow_rows=0,
            trade_rows=0,
            copy_rows=0,
            market_flow_hourly_rows=0,
            whale_flow_hourly_rows=0,
        ),
    ]

    plan = build_backfill_plan(rows, asset="ALL", min_volume=0.0, limit_markets=10)
    quick_ids = [row.market_id for row in plan[STAGE_1_QUICK]]

    assert quick_ids[:3] == ["btc-under", "btc-covered", "eth-under"]
    assert "sol-under" not in quick_ids


def test_stage_plan_generation() -> None:
    rows = [
        MarketCoverageRow(
            market_id=f"m-{asset.lower()}",
            market_slug=f"{asset.lower()}-market",
            asset=asset,
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=10_000.0,
            volume_total_usd=10_000.0,
            wallet_flow_rows=0,
            trade_rows=0,
            copy_rows=0,
            market_flow_hourly_rows=0,
            whale_flow_hourly_rows=0,
        )
        for asset in ("BTC", "ETH", "SOL", "XRP")
    ]
    plan = build_backfill_plan(rows, asset="ALL", min_volume=0.0, limit_markets=10)

    assert all(row.asset in {"BTC", "ETH"} for row in plan[STAGE_1_QUICK])
    assert len(plan[STAGE_2_DEPTH]) == 4
    assert len(plan[STAGE_3_BREADTH]) == 4


def test_dry_run_artifact_writing(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path / "warehouse")
    _seed_crypto_markets(paths)
    _seed_wallet_flow(paths)

    result = run_wallet_flow_backfill_plan(
        paths=paths,
        output_dir=tmp_path / "artifacts",
        asset="ALL",
        stage=STAGE_1_QUICK,
        execute=False,
        dry_run=True,
        limit_markets=10,
        limit_events=100,
    )

    assert result.execution is None
    assert result.artifacts.plan_md.exists()
    assert result.artifacts.plan_csv.exists()
    assert result.artifacts.coverage_csv.exists()
    assert "Mode: dry-run" in result.artifacts.plan_md.read_text()


def test_execute_mode_calls_existing_ingestor_with_planned_parameters(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path / "warehouse")
    _seed_crypto_markets(paths)
    _seed_wallet_flow(paths)
    calls: list[dict[str, object]] = []

    async def fake_runner(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return WalletFlowIngestResult(
            rows_written=25,
            trade_rows=24,
            copy_rows=1,
            markets_scanned=int(kwargs["limit_markets"]),
            markets_with_rows=3,
            skipped_markets=max(0, int(kwargs["limit_markets"]) - 3),
            source_clients=("fake.source",),
            warnings=("demo-warning",),
            shard_path="/tmp/fake.parquet",
        )

    result = run_wallet_flow_backfill_plan(
        paths=paths,
        output_dir=tmp_path / "artifacts",
        asset="ALL",
        stage=STAGE_1_QUICK,
        execute=True,
        dry_run=False,
        limit_markets=3,
        limit_events=500,
        ingest_runner=fake_runner,
    )

    assert len(calls) == 1
    assert calls[0]["limit_events"] == 500
    assert calls[0]["limit_markets"] == result.selected_stage_markets
    assert result.execution is not None
    assert result.execution.rows_written == 25
    assert "demo-warning" in result.execution.warnings


def test_repeated_run_prefers_undercovered_markets() -> None:
    rows = [
        MarketCoverageRow(
            market_id="m-under",
            market_slug="under",
            asset="BTC",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=50_000.0,
            volume_total_usd=50_000.0,
            wallet_flow_rows=0,
            trade_rows=0,
            copy_rows=0,
            market_flow_hourly_rows=0,
            whale_flow_hourly_rows=0,
        ),
        MarketCoverageRow(
            market_id="m-covered",
            market_slug="covered",
            asset="BTC",
            is_active=True,
            is_closed=False,
            is_archived=False,
            volume_1mo_usd=100_000.0,
            volume_total_usd=100_000.0,
            wallet_flow_rows=250,
            trade_rows=240,
            copy_rows=10,
            market_flow_hourly_rows=120,
            whale_flow_hourly_rows=100,
        ),
    ]

    plan = build_backfill_plan(rows, asset="ALL", min_volume=0.0, limit_markets=10)
    assert plan[STAGE_2_DEPTH][0].market_id == "m-under"


def test_empty_warehouse_behavior(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path / "warehouse")
    result = run_wallet_flow_backfill_plan(
        paths=paths,
        output_dir=tmp_path / "artifacts",
        asset="ALL",
        stage=STAGE_1_QUICK,
        execute=False,
        dry_run=True,
    )

    assert result.before.markets_total == 0
    assert result.selected_stage_markets == 0
    assert result.stage_counts[STAGE_1_QUICK] == 0
    assert result.stage_counts[STAGE_2_DEPTH] == 0
    assert result.stage_counts[STAGE_3_BREADTH] == 0
    assert result.artifacts.plan_md.exists()
