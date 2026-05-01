from __future__ import annotations

import csv

from joint_research.research.wallet_flow_backfill_batches import (
    render_wallet_flow_backfill_batches_report,
    run_wallet_flow_backfill_batches_plan,
    write_wallet_flow_backfill_batches_artifacts,
)
from joint_research.research.wallet_flow_backfill_priority import WalletFlowBackfillPriorityThresholds


def _write_coverage_csv(path, rows) -> None:
    header = [
        "market_id",
        "market_slug",
        "asset",
        "is_active",
        "is_closed",
        "is_archived",
        "volume_1mo_usd",
        "volume_total_usd",
        "wallet_flow_rows",
        "trade_rows",
        "copy_rows",
        "market_flow_hourly_rows",
        "whale_flow_hourly_rows",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_batches_respect_batch_size(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(
        coverage_csv,
        [
            {
                "market_id": "m1",
                "market_slug": "btc-market-1",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "1000",
                "volume_total_usd": "2000",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
            {
                "market_id": "m2",
                "market_slug": "btc-market-2",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "900",
                "volume_total_usd": "1900",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
            {
                "market_id": "m3",
                "market_slug": "eth-market-1",
                "asset": "ETH",
                "is_active": "False",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "800",
                "volume_total_usd": "1800",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
            # No backfill needed row (should be excluded by priority planner).
            {
                "market_id": "m4",
                "market_slug": "eth-market-2",
                "asset": "ETH",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "700",
                "volume_total_usd": "1700",
                "wallet_flow_rows": "24",
                "trade_rows": "24",
                "copy_rows": "0",
                "market_flow_hourly_rows": "24",
                "whale_flow_hourly_rows": "24",
            },
        ],
    )

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=24,
        min_market_flow_hourly_rows=24,
        min_whale_flow_hourly_rows=24,
    )
    plan = run_wallet_flow_backfill_batches_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=5,
        dry_run=True,
    )

    assert len(plan.rows) == 3
    assert len(plan.batches) == 2
    assert plan.batches[0].market_count == 2
    assert plan.batches[1].market_count == 1


def test_max_batches_limits_output(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(
        coverage_csv,
        [
            {
                "market_id": "m1",
                "market_slug": "btc-market-1",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "1000",
                "volume_total_usd": "2000",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
            {
                "market_id": "m2",
                "market_slug": "btc-market-2",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "900",
                "volume_total_usd": "1900",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
            {
                "market_id": "m3",
                "market_slug": "eth-market-1",
                "asset": "ETH",
                "is_active": "False",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "800",
                "volume_total_usd": "1800",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            },
        ],
    )

    thresholds = WalletFlowBackfillPriorityThresholds()
    plan = run_wallet_flow_backfill_batches_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
    )

    assert len(plan.batches) == 1
    assert len(plan.rows) == 2


def test_report_includes_safety_copy(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(
        coverage_csv,
        [
            {
                "market_id": "m1",
                "market_slug": "btc-market-1",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "1000",
                "volume_total_usd": "2000",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            }
        ],
    )
    thresholds = WalletFlowBackfillPriorityThresholds()
    plan = run_wallet_flow_backfill_batches_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=25,
        max_batches=5,
        dry_run=True,
    )
    report = render_wallet_flow_backfill_batches_report(plan)
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in report
    assert "No candidates promoted." in report
    assert "No threshold changes." in report
    assert "No live trading changes." in report
    assert "Dry-run planning only." in report


def test_writer_creates_md_and_csv(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(
        coverage_csv,
        [
            {
                "market_id": "m1",
                "market_slug": "btc-market-1",
                "asset": "BTC",
                "is_active": "True",
                "is_closed": "False",
                "is_archived": "False",
                "volume_1mo_usd": "1000",
                "volume_total_usd": "2000",
                "wallet_flow_rows": "0",
                "trade_rows": "0",
                "copy_rows": "0",
                "market_flow_hourly_rows": "0",
                "whale_flow_hourly_rows": "0",
            }
        ],
    )
    out_dir = tmp_path / "out"
    thresholds = WalletFlowBackfillPriorityThresholds()
    md_path, csv_path, plan = write_wallet_flow_backfill_batches_artifacts(
        coverage_csv=coverage_csv,
        output_dir=out_dir,
        thresholds=thresholds,
        batch_size=25,
        max_batches=5,
        dry_run=True,
    )
    assert md_path.exists()
    assert csv_path.exists()
    assert plan.dry_run is True

