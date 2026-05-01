from __future__ import annotations

import csv

from joint_research.research.wallet_flow_backfill_manifest import (
    REVIEW_ECHO_COMMAND_TEMPLATE,
    run_wallet_flow_backfill_manifest_plan,
    write_wallet_flow_backfill_manifest_artifacts,
)
from joint_research.research.wallet_flow_backfill_priority import WalletFlowBackfillPriorityThresholds
from joint_research.research.wallet_flow_manifest_review_gate import run_wallet_flow_manifest_review_gate


def _write_coverage_csv(path, n_rows: int = 3) -> None:
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
            )


def test_review_echo_preset_creates_review_ready_rows(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )

    assert plan.command_template == REVIEW_ECHO_COMMAND_TEMPLATE
    assert plan.rows
    assert all(row.command_status == "REVIEW_READY" for row in plan.rows)


def test_review_echo_command_renders_expected_fields_and_is_safe(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=1,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )

    command = plan.rows[0].ingest_command
    assert "review_wallet_flow_backfill" in command
    assert f"market_id={plan.rows[0].market_id}" in command
    assert f"market_slug={plan.rows[0].market_slug}" in command
    assert f"asset={plan.rows[0].asset}" in command
    assert f"batch_id={plan.rows[0].batch_id}" in command
    assert f"rank={plan.rows[0].rank}" in command
    for op in (";", "&&", "||", "`", "$(", "<", ">", "|"):
        assert op not in command


def test_review_echo_manifest_passes_review_gate(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, json_path, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "out",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )
    gate = run_wallet_flow_manifest_review_gate(
        manifest_json=json_path,
        output_dir=tmp_path / "gate",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert gate.status == "PASS"


def test_default_manifest_requires_allow_review_required(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, json_path, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "out",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
    )

    fail_gate = run_wallet_flow_manifest_review_gate(
        manifest_json=json_path,
        output_dir=tmp_path / "gate_fail",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert fail_gate.status == "FAIL"

    pass_gate = run_wallet_flow_manifest_review_gate(
        manifest_json=json_path,
        output_dir=tmp_path / "gate_pass",
        allow_review_required=True,
        require_dry_run=True,
    )
    assert pass_gate.status == "PASS"
