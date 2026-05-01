from __future__ import annotations

import csv

from joint_research.research.wallet_flow_backfill_manifest import (
    run_wallet_flow_backfill_manifest_plan,
    write_wallet_flow_backfill_manifest_artifacts,
)
from joint_research.research.wallet_flow_backfill_priority import WalletFlowBackfillPriorityThresholds


def _write_coverage_csv(path, n_rows: int) -> None:
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
        for i in range(1, n_rows + 1):
            writer.writerow(
                {
                    "market_id": f"m{i}",
                    "market_slug": f"market-{i}",
                    "asset": "BTC" if i % 2 else "ETH",
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
            )


def test_manifest_row_count_follows_batch_size_max_batches(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=10)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=3,
        dry_run=True,
        command_template=None,
    )
    assert len(plan.rows) == 6
    assert plan.batches == 3


def test_manifest_id_deterministic(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=10)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan1 = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    plan2 = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    assert plan1.manifest_id == plan2.manifest_id


def test_idempotency_key_deterministic(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=5)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    keys = [row.idempotency_key for row in plan.rows]
    plan_again = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    assert keys == [row.idempotency_key for row in plan_again.rows]


def test_row_checksum_deterministic(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=5)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan1 = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    plan2 = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=2,
        dry_run=True,
        command_template=None,
    )
    assert [row.row_checksum for row in plan1.rows] == [row.row_checksum for row in plan2.rows]


def test_command_template_rendering(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=3)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template="echo {batch_id} {rank} {asset} {market_id} {market_slug}",
    )
    assert plan.rows[0].command_status == "TEMPLATE"
    assert plan.rows[0].ingest_command.startswith("echo ")


def test_no_template_mode_is_review_required(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=3)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template=None,
    )
    assert plan.rows
    assert plan.rows[0].command_status == "REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED:" in plan.rows[0].ingest_command


def test_writer_creates_md_csv_json(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv, n_rows=3)
    thresholds = WalletFlowBackfillPriorityThresholds()

    out_dir = tmp_path / "out"
    md_path, csv_path, json_path, plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=out_dir,
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template=None,
    )
    assert md_path.exists()
    assert csv_path.exists()
    assert json_path.exists()
    assert plan.manifest_id

