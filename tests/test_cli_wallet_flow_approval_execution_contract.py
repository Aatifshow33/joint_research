from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _payloads() -> tuple[dict, dict, dict]:
    ledger = {
        "ledger_status": "PENDING_MANUAL_REVIEW",
        "decision": "pending",
        "reviewer": "manual-operator",
        "review_note": "pending",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
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
    }
    handoff = {
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
    }
    plan = {
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
    }
    return ledger, handoff, plan


def test_wallet_flow_approval_execution_contract_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-approval-execution-contract", "--help"])

    assert result.exit_code == 0
    assert "--approval-ledger-json" in result.output
    assert "--guarded-handoff-json" in result.output
    assert "--dry-run-plan-json" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_outputs_and_prints_contract_status(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    out_dir = tmp_path / "out"
    ledger, handoff, plan = _payloads()
    _write_json(ledger_json, ledger)
    _write_json(handoff_json, handoff)
    _write_json(plan_json, plan)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-approval-execution-contract",
            "--approval-ledger-json",
            str(ledger_json),
            "--guarded-handoff-json",
            str(handoff_json),
            "--dry-run-plan-json",
            str(plan_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "contract_status=AWAITING_APPROVAL" in result.output
    assert "ledger_status=PENDING_MANUAL_REVIEW" in result.output
    assert "decision=pending" in result.output
    assert "handoff_status=READY_FOR_MANUAL_APPROVAL" in result.output
    assert "plan_status=READY" in result.output
    assert "approval_required=true" in result.output
    assert "manual_operator_only=true" in result.output
    assert "no_execution=true" in result.output
    assert "no_ingestion=true" in result.output
    assert "live_adapter_enabled=false" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "approval_execution_contract=" in result.output
    assert "approval_execution_contract_json=" in result.output

    assert (out_dir / "wallet_flow_approval_execution_contract.md").exists()
    assert (out_dir / "wallet_flow_approval_execution_contract.json").exists()


def test_cli_blocked_when_ledger_missing(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    out_dir = tmp_path / "out"
    _, handoff, plan = _payloads()
    _write_json(handoff_json, handoff)
    _write_json(plan_json, plan)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-approval-execution-contract",
            "--approval-ledger-json",
            str(tmp_path / "missing-ledger.json"),
            "--guarded-handoff-json",
            str(handoff_json),
            "--dry-run-plan-json",
            str(plan_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "contract_status=BLOCKED" in result.output
    assert "ledger_status=MISSING" in result.output
    assert "decision=unknown" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
