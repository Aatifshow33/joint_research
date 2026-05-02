from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_text(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_wallet_flow_manifest_audit_index_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-manifest-audit-index", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output
    assert "--coverage-gate-report" in result.output
    assert "--priority-report" in result.output
    assert "--batch-report" in result.output
    assert "--manifest-report" in result.output
    assert "--review-gate-report" in result.output
    assert "--approved-packet-report" in result.output
    assert "--manifest-json" in result.output
    assert "--approved-packet-json" in result.output


def test_cli_writes_outputs_and_prints_ready_status(tmp_path) -> None:
    out_dir = tmp_path / "out"

    manifest_json = out_dir / "wallet_flow_backfill_execution_manifest.json"
    approved_packet_json = out_dir / "wallet_flow_approved_manifest_packet.json"
    _write_text(
        manifest_json,
        json.dumps(
            {
                "manifest_id": "mfest",
                "manifest_rows": 1,
                "dry_run": True,
                "rows": [
                    {
                        "batch_id": 1,
                        "rank": 1,
                        "command_status": "REVIEW_READY",
                        "idempotency_key": "k1",
                        "row_checksum": "c1",
                    }
                ],
            }
        ),
    )
    _write_text(
        approved_packet_json,
        json.dumps(
            {
                "export_status": "PASS",
                "gate_status": "PASS",
                "manifest_rows": 1,
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-manifest-audit-index",
            "--output-dir",
            str(out_dir),
            "--manifest-json",
            str(manifest_json),
            "--approved-packet-json",
            str(approved_packet_json),
            "--coverage-gate-report",
            str(out_dir / "wallet_flow_coverage_gate.md"),
            "--priority-report",
            str(out_dir / "wallet_flow_backfill_priority.md"),
            "--batch-report",
            str(out_dir / "wallet_flow_backfill_batches.md"),
            "--manifest-report",
            str(out_dir / "wallet_flow_backfill_execution_manifest.md"),
            "--review-gate-report",
            str(out_dir / "wallet_flow_manifest_review_gate.md"),
            "--approved-packet-report",
            str(out_dir / "wallet_flow_approved_manifest_packet.md"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "audit_status=READY" in result.output
    assert "reports_found=" in result.output
    assert "reports_missing=" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "audit_index=" in result.output
    assert "audit_index_json=" in result.output

    assert (out_dir / "wallet_flow_manifest_audit_index.md").exists()
    assert (out_dir / "wallet_flow_manifest_audit_index.json").exists()


def test_cli_blocked_when_approved_packet_missing(tmp_path) -> None:
    out_dir = tmp_path / "out"
    manifest_json = out_dir / "wallet_flow_backfill_execution_manifest.json"
    _write_text(
        manifest_json,
        json.dumps(
            {
                "manifest_id": "mfest",
                "manifest_rows": 1,
                "dry_run": True,
                "rows": [],
            }
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-manifest-audit-index",
            "--output-dir",
            str(out_dir),
            "--manifest-json",
            str(manifest_json),
            "--approved-packet-json",
            str(out_dir / "missing_approved_packet.json"),
            "--coverage-gate-report",
            str(out_dir / "wallet_flow_coverage_gate.md"),
            "--priority-report",
            str(out_dir / "wallet_flow_backfill_priority.md"),
            "--batch-report",
            str(out_dir / "wallet_flow_backfill_batches.md"),
            "--manifest-report",
            str(out_dir / "wallet_flow_backfill_execution_manifest.md"),
            "--review-gate-report",
            str(out_dir / "wallet_flow_manifest_review_gate.md"),
            "--approved-packet-report",
            str(out_dir / "wallet_flow_approved_manifest_packet.md"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "audit_status=BLOCKED" in result.output
    assert "No ingestion executed." in result.output
