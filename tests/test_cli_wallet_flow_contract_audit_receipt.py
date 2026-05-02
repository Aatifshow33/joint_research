from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _payloads() -> tuple[dict, dict, dict, dict, dict, dict]:
    contract = {
        "contract_status": "AWAITING_APPROVAL",
        "ledger_status": "PENDING_MANUAL_REVIEW",
        "decision": "pending",
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
        "adapter_contract_version": "wallet_flow_execution_contract_v1",
        "execution_mode": "contract_only",
        "approval_required": True,
        "manual_operator_only": True,
        "no_execution": True,
        "no_ingestion": True,
        "live_adapter_enabled": False,
        "planned_rows": [
            {
                "batch_id": 1,
                "rank": 1,
                "asset": "BTC",
                "market_id": "m1",
                "market_slug": "market-1",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "idempotency_key": "k1",
                "row_checksum": "c1",
                "command": "review_wallet_flow_backfill market_id=m1",
            }
        ],
    }
    ledger = {
        "ledger_status": "PENDING_MANUAL_REVIEW",
        "decision": "pending",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
    }
    handoff = {
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
    }
    plan = {
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_rows": [],
    }
    approved_packet = {"export_status": "PASS", "manifest_rows": 1, "manifest_id": "mfest-1"}
    audit_index = {"audit_status": "READY", "manifest_rows": 1}
    return contract, ledger, handoff, plan, approved_packet, audit_index


def test_wallet_flow_contract_audit_receipt_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-contract-audit-receipt", "--help"])

    assert result.exit_code == 0
    assert "Approval execution contract" in result.output
    assert "--approval-ledger-json" in result.output
    assert "--guarded-handoff-json" in result.output
    assert "--dry-run-plan-json" in result.output
    assert "--approved-packet-json" in result.output
    assert "--audit-index-json" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_outputs_and_prints_receipt_status(tmp_path) -> None:
    contract_json = tmp_path / "contract.json"
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "packet.json"
    audit_index_json = tmp_path / "audit.json"
    out_dir = tmp_path / "out"
    contract, ledger, handoff, plan, packet, audit = _payloads()
    _write_json(contract_json, contract)
    _write_json(ledger_json, ledger)
    _write_json(handoff_json, handoff)
    _write_json(plan_json, plan)
    _write_json(approved_packet_json, packet)
    _write_json(audit_index_json, audit)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-contract-audit-receipt",
            "--approval-execution-contract-json",
            str(contract_json),
            "--approval-ledger-json",
            str(ledger_json),
            "--guarded-handoff-json",
            str(handoff_json),
            "--dry-run-plan-json",
            str(plan_json),
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
    assert "receipt_status=AWAITING_APPROVAL" in result.output
    assert "contract_status=AWAITING_APPROVAL" in result.output
    assert "ledger_status=PENDING_MANUAL_REVIEW" in result.output
    assert "decision=pending" in result.output
    assert "handoff_status=READY_FOR_MANUAL_APPROVAL" in result.output
    assert "plan_status=READY" in result.output
    assert "approved_packet_status=PASS" in result.output
    assert "audit_status=READY" in result.output
    assert "approval_required=true" in result.output
    assert "manual_operator_only=true" in result.output
    assert "no_execution=true" in result.output
    assert "no_ingestion=true" in result.output
    assert "live_adapter_enabled=false" in result.output
    assert "no_orders=true" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "contract_audit_receipt=" in result.output
    assert "contract_audit_receipt_json=" in result.output

    assert (out_dir / "wallet_flow_contract_audit_receipt.md").exists()
    assert (out_dir / "wallet_flow_contract_audit_receipt.json").exists()


def test_cli_blocked_when_contract_missing(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "packet.json"
    audit_index_json = tmp_path / "audit.json"
    out_dir = tmp_path / "out"
    _, ledger, handoff, plan, packet, audit = _payloads()
    _write_json(ledger_json, ledger)
    _write_json(handoff_json, handoff)
    _write_json(plan_json, plan)
    _write_json(approved_packet_json, packet)
    _write_json(audit_index_json, audit)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-contract-audit-receipt",
            "--approval-execution-contract-json",
            str(tmp_path / "missing-contract.json"),
            "--approval-ledger-json",
            str(ledger_json),
            "--guarded-handoff-json",
            str(handoff_json),
            "--dry-run-plan-json",
            str(plan_json),
            "--approved-packet-json",
            str(approved_packet_json),
            "--audit-index-json",
            str(audit_index_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "receipt_status=BLOCKED" in result.output
    assert "contract_status=MISSING" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
