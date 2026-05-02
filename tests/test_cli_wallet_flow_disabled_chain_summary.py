from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _contract_payload() -> dict:
    return {
        "contract_status": "CONTRACT_READY",
        "ledger_status": "APPROVED",
        "decision": "approve",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
    }


def _receipt_payload() -> dict:
    return {
        "receipt_status": "RECEIPT_READY",
        "contract_status": "CONTRACT_READY",
        "ledger_status": "APPROVED",
        "decision": "approve",
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
    }


def _adapter_payload() -> dict:
    return {
        "adapter_status": "DISABLED_BY_POLICY",
        "receipt_status": "RECEIPT_READY",
        "contract_status": "CONTRACT_READY",
        "ledger_status": "APPROVED",
        "decision": "approve",
        "adapter_enabled": False,
        "execution_enabled": False,
        "network_enabled": False,
        "ingestion_enabled": False,
        "shell_enabled": False,
        "order_placement_enabled": False,
        "database_mutation_enabled": False,
        "approval_required": True,
        "manual_operator_only": True,
        "no_execution": True,
        "no_ingestion": True,
        "no_orders": True,
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
    }


def _run_payload() -> dict:
    return {
        "run_status": "DISABLED_BY_POLICY_CONFIRMED",
        "adapter_status": "DISABLED_BY_POLICY",
        "receipt_status": "RECEIPT_READY",
        "contract_status": "CONTRACT_READY",
        "ledger_status": "APPROVED",
        "decision": "approve",
        "adapter_enabled": False,
        "execution_enabled": False,
        "network_enabled": False,
        "ingestion_enabled": False,
        "shell_enabled": False,
        "order_placement_enabled": False,
        "database_mutation_enabled": False,
        "approval_required": True,
        "manual_operator_only": True,
        "no_execution": True,
        "no_ingestion": True,
        "no_orders": True,
        "manifest_id": "mfest-1",
        "manifest_rows": 1,
        "planned_row_count": 1,
        "run_rows": [
            {
                "batch_id": 1,
                "rank": 1,
                "asset": "BTC",
                "market_id": "m1",
                "market_slug": "market-1",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "receipt_row_status": "RECEIPT_ROW_READY",
                "adapter_row_status": "DISABLED_BY_POLICY",
                "run_row_status": "DISABLED_BY_POLICY_CONFIRMED",
                "idempotency_key": "k1",
                "row_checksum": "c1",
                "command": "review_wallet_flow_backfill market_id=m1",
            }
        ],
    }


def test_wallet_flow_disabled_chain_summary_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-disabled-chain-summary", "--help"])

    assert result.exit_code == 0
    assert "Approval execution contract" in result.output
    assert "--contract-audit-receipt-json" in result.output
    assert "Disabled adapter interface JSON" in result.output
    assert "Disabled adapter run receipt" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_outputs_and_prints_chain_status(tmp_path) -> None:
    contract_json = tmp_path / "contract.json"
    receipt_json = tmp_path / "receipt.json"
    adapter_json = tmp_path / "adapter.json"
    run_json = tmp_path / "run.json"
    out_dir = tmp_path / "out"
    _write_json(contract_json, _contract_payload())
    _write_json(receipt_json, _receipt_payload())
    _write_json(adapter_json, _adapter_payload())
    _write_json(run_json, _run_payload())

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-disabled-chain-summary",
            "--approval-execution-contract-json",
            str(contract_json),
            "--contract-audit-receipt-json",
            str(receipt_json),
            "--disabled-adapter-interface-json",
            str(adapter_json),
            "--disabled-adapter-run-receipt-json",
            str(run_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "chain_status=DISABLED_CHAIN_CONFIRMED" in result.output
    assert "contract_status=CONTRACT_READY" in result.output
    assert "receipt_status=RECEIPT_READY" in result.output
    assert "adapter_status=DISABLED_BY_POLICY" in result.output
    assert "run_status=DISABLED_BY_POLICY_CONFIRMED" in result.output
    assert "ledger_status=APPROVED" in result.output
    assert "decision=approve" in result.output
    assert "adapter_enabled=false" in result.output
    assert "execution_enabled=false" in result.output
    assert "network_enabled=false" in result.output
    assert "ingestion_enabled=false" in result.output
    assert "shell_enabled=false" in result.output
    assert "order_placement_enabled=false" in result.output
    assert "database_mutation_enabled=false" in result.output
    assert "approval_required=true" in result.output
    assert "manual_operator_only=true" in result.output
    assert "no_execution=true" in result.output
    assert "no_ingestion=true" in result.output
    assert "no_orders=true" in result.output
    assert "disabled_reason=DISABLED_BY_POLICY" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "disabled_chain_summary=" in result.output
    assert "disabled_chain_summary_json=" in result.output

    assert (out_dir / "wallet_flow_disabled_chain_summary.md").exists()
    assert (out_dir / "wallet_flow_disabled_chain_summary.json").exists()


def test_cli_blocked_when_contract_missing(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    adapter_json = tmp_path / "adapter.json"
    run_json = tmp_path / "run.json"
    out_dir = tmp_path / "out"
    _write_json(receipt_json, _receipt_payload())
    _write_json(adapter_json, _adapter_payload())
    _write_json(run_json, _run_payload())

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-disabled-chain-summary",
            "--approval-execution-contract-json",
            str(tmp_path / "missing-contract.json"),
            "--contract-audit-receipt-json",
            str(receipt_json),
            "--disabled-adapter-interface-json",
            str(adapter_json),
            "--disabled-adapter-run-receipt-json",
            str(run_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "chain_status=BLOCKED" in result.output
    assert "contract_status=MISSING" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
