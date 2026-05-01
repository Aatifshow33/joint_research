from __future__ import annotations

import csv

from joint_research.research.wallet_flow_approved_manifest_packet import (
    build_wallet_flow_approved_manifest_packet,
    write_wallet_flow_approved_manifest_packet,
)
from joint_research.research.wallet_flow_backfill_manifest import (
    write_wallet_flow_backfill_manifest_artifacts,
)
from joint_research.research.wallet_flow_backfill_priority import WalletFlowBackfillPriorityThresholds


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


def test_review_echo_manifest_creates_pass_packet(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, manifest_json, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "manifest",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )

    artifacts = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "manifest" / "wallet_flow_manifest_review_gate.md",
        output_dir=tmp_path / "packet",
    )

    assert artifacts.packet.export_status == "PASS"
    assert artifacts.packet.gate_status == "PASS"
    assert artifacts.packet_md.exists()
    assert artifacts.packet_json.exists()


def test_default_review_required_manifest_creates_blocked_packet(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, manifest_json, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "manifest",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
    )

    packet = build_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "manifest" / "wallet_flow_manifest_review_gate.md",
        output_dir=tmp_path / "packet",
    )
    assert packet.export_status == "BLOCKED"
    assert packet.gate_status == "FAIL"
    assert packet.failure_reasons


def test_missing_manifest_creates_blocked_packet(tmp_path) -> None:
    artifacts = write_wallet_flow_approved_manifest_packet(
        manifest_json=tmp_path / "missing_manifest.json",
        review_gate_report=tmp_path / "missing_gate.md",
        output_dir=tmp_path / "packet",
    )
    assert artifacts.packet.export_status == "BLOCKED"
    assert artifacts.packet.gate_status == "FAIL"


def test_invalid_manifest_json_creates_blocked_packet(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    manifest_json.write_text("{not json")

    artifacts = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "missing_gate.md",
        output_dir=tmp_path / "packet",
    )
    assert artifacts.packet.export_status == "BLOCKED"
    assert artifacts.packet.gate_status == "FAIL"


def test_packet_includes_safety_copy_and_human_review_text(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, manifest_json, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "manifest",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )

    artifacts = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "manifest" / "wallet_flow_manifest_review_gate.md",
        output_dir=tmp_path / "packet",
    )
    text = artifacts.packet_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "No ingestion executed." in text
    assert "Approved for human review only." in text


def test_json_output_is_deterministic(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    thresholds = WalletFlowBackfillPriorityThresholds()

    _md, _csv, manifest_json, _plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "manifest",
        thresholds=thresholds,
        batch_size=2,
        max_batches=1,
        dry_run=True,
        command_template_preset="review_echo",
    )

    out_dir = tmp_path / "packet"
    first = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "manifest" / "wallet_flow_manifest_review_gate.md",
        output_dir=out_dir,
    )
    first_json = first.packet_json.read_text()

    second = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=tmp_path / "manifest" / "wallet_flow_manifest_review_gate.md",
        output_dir=out_dir,
    )
    second_json = second.packet_json.read_text()

    assert first_json == second_json
