from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_wallet_flow_guarded_operator_handoff_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-guarded-operator-handoff", "--help"])

    assert result.exit_code == 0
    assert "--dry-run-plan-json" in result.output
    assert "--approved-packet-json" in result.output
    assert "--audit-index-json" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_outputs_and_prints_handoff_status(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    out_dir = tmp_path / "out"

    _write_json(
        dry_run_plan_json,
        {
            "plan_status": "READY",
            "manifest_id": "mfest-1",
            "manifest_rows": 1,
            "batch_count": 1,
            "command_status_counts": [{"command_status": "REVIEW_READY", "count": 1}],
            "planned_rows": [
                {
                    "batch_id": 1,
                    "rank": 1,
                    "asset": "BTC",
                    "market_id": "m1",
                    "market_slug": "market-1",
                    "command_status": "REVIEW_READY",
                    "idempotency_key": "k1",
                    "row_checksum": "c1",
                    "command": "review_wallet_flow_backfill market_id=m1",
                }
            ],
        },
    )
    _write_json(approved_packet_json, {"export_status": "PASS"})
    _write_json(audit_index_json, {"audit_status": "READY"})

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-guarded-operator-handoff",
            "--dry-run-plan-json",
            str(dry_run_plan_json),
            "--approved-packet-json",
            str(approved_packet_json),
            "--audit-index-json",
            str(audit_index_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "handoff_status=READY_FOR_MANUAL_APPROVAL" in result.output
    assert "plan_status=READY" in result.output
    assert "approved_packet_status=PASS" in result.output
    assert "audit_status=READY" in result.output
    assert "approval_required=true" in result.output
    assert "manual_operator_only=true" in result.output
    assert "no_execution=true" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "guarded_operator_handoff=" in result.output
    assert "guarded_operator_handoff_json=" in result.output

    assert (out_dir / "wallet_flow_guarded_operator_handoff.md").exists()
    assert (out_dir / "wallet_flow_guarded_operator_handoff.json").exists()


def test_cli_blocked_when_inputs_missing(tmp_path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-guarded-operator-handoff",
            "--dry-run-plan-json",
            str(tmp_path / "missing-plan.json"),
            "--approved-packet-json",
            str(tmp_path / "missing-approved.json"),
            "--audit-index-json",
            str(tmp_path / "missing-audit.json"),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_status=BLOCKED" in result.output
    assert "plan_status=MISSING" in result.output
    assert "approved_packet_status=MISSING" in result.output
    assert "audit_status=MISSING" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
