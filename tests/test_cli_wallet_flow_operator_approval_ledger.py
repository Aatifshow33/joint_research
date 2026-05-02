from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_wallet_flow_operator_approval_ledger_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-operator-approval-ledger", "--help"])

    assert result.exit_code == 0
    assert "--guarded-handoff-json" in result.output
    assert "--decision" in result.output
    assert "--reviewer" in result.output
    assert "--review-note" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_outputs_and_prints_ledger_status(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    out_dir = tmp_path / "out"
    _write_json(
        handoff_json,
        {
            "handoff_status": "READY_FOR_MANUAL_APPROVAL",
            "plan_status": "READY",
            "approved_packet_status": "PASS",
            "audit_status": "READY",
            "manifest_id": "mfest-1",
            "manifest_rows": 1,
            "planned_row_count": 1,
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

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-operator-approval-ledger",
            "--guarded-handoff-json",
            str(handoff_json),
            "--decision",
            "pending",
            "--reviewer",
            "manual-operator",
            "--review-note",
            "Phase 4.22 validation only",
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "ledger_status=PENDING_MANUAL_REVIEW" in result.output
    assert "decision=pending" in result.output
    assert "handoff_status=READY_FOR_MANUAL_APPROVAL" in result.output
    assert "approval_required=true" in result.output
    assert "manual_operator_only=true" in result.output
    assert "no_execution=true" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "operator_approval_ledger=" in result.output
    assert "operator_approval_ledger_json=" in result.output

    assert (out_dir / "wallet_flow_operator_approval_ledger.md").exists()
    assert (out_dir / "wallet_flow_operator_approval_ledger.json").exists()


def test_cli_blocked_when_handoff_missing(tmp_path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-operator-approval-ledger",
            "--guarded-handoff-json",
            str(tmp_path / "missing-handoff.json"),
            "--decision",
            "approve",
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ledger_status=BLOCKED" in result.output
    assert "decision=approve" in result.output
    assert "handoff_status=MISSING" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output


def test_cli_invalid_decision_fails_clearly(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, {"handoff_status": "READY_FOR_MANUAL_APPROVAL"})

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-operator-approval-ledger",
            "--guarded-handoff-json",
            str(handoff_json),
            "--decision",
            "ship",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for --decision" in result.output
