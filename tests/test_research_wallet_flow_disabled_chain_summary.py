from __future__ import annotations

import json

from joint_research.research.wallet_flow_disabled_chain_summary import (
    build_wallet_flow_disabled_chain_summary,
    write_wallet_flow_disabled_chain_summary,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _contract_payload(*, contract_status: str = "CONTRACT_READY", rows: int = 2) -> dict:
    return {
        "contract_status": contract_status,
        "ledger_status": "APPROVED" if contract_status == "CONTRACT_READY" else "PENDING_MANUAL_REVIEW",
        "decision": "approve" if contract_status == "CONTRACT_READY" else "pending",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
    }


def _receipt_payload(*, receipt_status: str = "RECEIPT_READY", rows: int = 2) -> dict:
    return {
        "receipt_status": receipt_status,
        "contract_status": "CONTRACT_READY" if receipt_status == "RECEIPT_READY" else "AWAITING_APPROVAL",
        "ledger_status": "APPROVED" if receipt_status == "RECEIPT_READY" else "PENDING_MANUAL_REVIEW",
        "decision": "approve" if receipt_status == "RECEIPT_READY" else "pending",
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
        "receipt_rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "receipt_row_status": "RECEIPT_ROW_READY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _adapter_payload(*, adapter_status: str = "DISABLED_BY_POLICY", rows: int = 2) -> dict:
    return {
        "adapter_status": adapter_status,
        "receipt_status": "RECEIPT_READY" if adapter_status == "DISABLED_BY_POLICY" else "AWAITING_APPROVAL",
        "contract_status": "CONTRACT_READY" if adapter_status == "DISABLED_BY_POLICY" else "AWAITING_APPROVAL",
        "ledger_status": "APPROVED" if adapter_status == "DISABLED_BY_POLICY" else "PENDING_MANUAL_REVIEW",
        "decision": "approve" if adapter_status == "DISABLED_BY_POLICY" else "pending",
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
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
        "adapter_preview_rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "receipt_row_status": "RECEIPT_ROW_READY",
                "adapter_row_status": "DISABLED_BY_POLICY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _run_payload(*, run_status: str = "DISABLED_BY_POLICY_CONFIRMED", rows: int = 2) -> dict:
    return {
        "run_status": run_status,
        "adapter_status": "DISABLED_BY_POLICY" if run_status == "DISABLED_BY_POLICY_CONFIRMED" else "AWAITING_APPROVAL",
        "receipt_status": "RECEIPT_READY" if run_status == "DISABLED_BY_POLICY_CONFIRMED" else "AWAITING_APPROVAL",
        "contract_status": "CONTRACT_READY" if run_status == "DISABLED_BY_POLICY_CONFIRMED" else "AWAITING_APPROVAL",
        "ledger_status": "APPROVED" if run_status == "DISABLED_BY_POLICY_CONFIRMED" else "PENDING_MANUAL_REVIEW",
        "decision": "approve" if run_status == "DISABLED_BY_POLICY_CONFIRMED" else "pending",
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
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
        "run_rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "receipt_row_status": "RECEIPT_ROW_READY",
                "adapter_row_status": "DISABLED_BY_POLICY",
                "run_row_status": "DISABLED_BY_POLICY_CONFIRMED",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _write_all(tmp_path, *, contract: dict, receipt: dict, adapter: dict, run: dict):
    contract_json = tmp_path / "contract.json"
    receipt_json = tmp_path / "receipt.json"
    adapter_json = tmp_path / "adapter.json"
    run_json = tmp_path / "run.json"
    _write_json(contract_json, contract)
    _write_json(receipt_json, receipt)
    _write_json(adapter_json, adapter)
    _write_json(run_json, run)
    return contract_json, receipt_json, adapter_json, run_json


def test_confirmed_chain_yields_disabled_chain_confirmed(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(),
        receipt=_receipt_payload(),
        adapter=_adapter_payload(),
        run=_run_payload(),
    )
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=paths[0],
        contract_audit_receipt_json=paths[1],
        disabled_adapter_interface_json=paths[2],
        disabled_adapter_run_receipt_json=paths[3],
    )
    assert summary.chain_status == "DISABLED_CHAIN_CONFIRMED"


def test_any_awaiting_stage_yields_awaiting_approval(tmp_path) -> None:
    run = _run_payload(run_status="AWAITING_APPROVAL")
    run["adapter_status"] = "AWAITING_APPROVAL"
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(contract_status="AWAITING_APPROVAL"),
        receipt=_receipt_payload(receipt_status="AWAITING_APPROVAL"),
        adapter=_adapter_payload(adapter_status="AWAITING_APPROVAL"),
        run=run,
    )
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=paths[0],
        contract_audit_receipt_json=paths[1],
        disabled_adapter_interface_json=paths[2],
        disabled_adapter_run_receipt_json=paths[3],
    )
    assert summary.chain_status == "AWAITING_APPROVAL"


def test_any_rejected_stage_yields_rejected(tmp_path) -> None:
    run = _run_payload(run_status="REJECTED")
    run["adapter_status"] = "REJECTED"
    run["receipt_status"] = "REJECTED"
    run["contract_status"] = "REJECTED"
    run["ledger_status"] = "REJECTED"
    run["decision"] = "reject"
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(contract_status="REJECTED"),
        receipt=_receipt_payload(receipt_status="REJECTED"),
        adapter=_adapter_payload(adapter_status="REJECTED"),
        run=run,
    )
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=paths[0],
        contract_audit_receipt_json=paths[1],
        disabled_adapter_interface_json=paths[2],
        disabled_adapter_run_receipt_json=paths[3],
    )
    assert summary.chain_status == "REJECTED"


def test_missing_inputs_each_yield_blocked(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(),
        receipt=_receipt_payload(),
        adapter=_adapter_payload(),
        run=_run_payload(),
    )
    for idx in range(4):
        args = list(paths)
        args[idx] = tmp_path / f"missing-{idx}.json"
        summary = build_wallet_flow_disabled_chain_summary(
            approval_execution_contract_json=args[0],
            contract_audit_receipt_json=args[1],
            disabled_adapter_interface_json=args[2],
            disabled_adapter_run_receipt_json=args[3],
        )
        assert summary.chain_status == "BLOCKED"


def test_invalid_json_yields_blocked_with_warning(tmp_path) -> None:
    contract_json = tmp_path / "contract.json"
    receipt_json = tmp_path / "receipt.json"
    adapter_json = tmp_path / "adapter.json"
    run_json = tmp_path / "run.json"
    _write_json(contract_json, _contract_payload())
    _write_json(receipt_json, _receipt_payload())
    _write_json(adapter_json, _adapter_payload())
    run_json.write_text("{not json")
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=contract_json,
        contract_audit_receipt_json=receipt_json,
        disabled_adapter_interface_json=adapter_json,
        disabled_adapter_run_receipt_json=run_json,
    )
    assert summary.chain_status == "BLOCKED"
    assert any("disabled_adapter_run_receipt_json_invalid_json" in warning for warning in summary.warnings)


def test_inconsistent_manifest_values_yield_blocked(tmp_path) -> None:
    contract = _contract_payload()
    receipt = _receipt_payload()
    adapter = _adapter_payload()
    run = _run_payload()
    receipt["manifest_id"] = "mfest-2"
    adapter["manifest_rows"] = 3
    run["planned_row_count"] = 4
    paths = _write_all(tmp_path, contract=contract, receipt=receipt, adapter=adapter, run=run)
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=paths[0],
        contract_audit_receipt_json=paths[1],
        disabled_adapter_interface_json=paths[2],
        disabled_adapter_run_receipt_json=paths[3],
    )
    assert summary.chain_status == "BLOCKED"
    failed = {check.name for check in summary.chain_checks if check.status == "FAIL"}
    assert "manifest_id_consistent" in failed
    assert "manifest_rows_consistent" in failed
    assert "planned_row_count_consistent" in failed


def test_flags_versions_source_artifacts_rows_and_safety_copy(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(rows=12),
        receipt=_receipt_payload(rows=12),
        adapter=_adapter_payload(rows=12),
        run=_run_payload(rows=12),
    )
    artifacts = write_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=paths[0],
        contract_audit_receipt_json=paths[1],
        disabled_adapter_interface_json=paths[2],
        disabled_adapter_run_receipt_json=paths[3],
        output_dir=tmp_path / "out",
    )
    summary = artifacts.summary
    assert summary.adapter_enabled is False
    assert summary.execution_enabled is False
    assert summary.network_enabled is False
    assert summary.ingestion_enabled is False
    assert summary.shell_enabled is False
    assert summary.order_placement_enabled is False
    assert summary.database_mutation_enabled is False
    assert summary.approval_required is True
    assert summary.manual_operator_only is True
    assert summary.no_execution is True
    assert summary.no_ingestion is True
    assert summary.no_orders is True
    assert summary.chain_summary_version == "wallet_flow_disabled_chain_summary_v1"
    assert summary.execution_mode == "disabled_chain_summary_only"
    assert summary.disabled_reason == "DISABLED_BY_POLICY"
    assert summary.final_confirmation == "Wallet-flow chain is disabled by policy; no execution was attempted."
    assert len(summary.source_artifacts) == 4
    assert all(source.state == "OK" for source in summary.source_artifacts)
    assert all(source.size_bytes is not None for source in summary.source_artifacts)
    assert all(source.sha256 is not None for source in summary.source_artifacts)
    assert summary.chain_checks
    assert len(summary.chain_rows) == 10
    assert all(row.command.startswith("review_wallet_flow_backfill") for row in summary.chain_rows)
    assert all(row.chain_row_status == "DISABLED_CHAIN_CONFIRMED" for row in summary.chain_rows)

    text = artifacts.summary_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Disabled chain summary only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Chain is disabled by policy." in text
    assert "Summary records disabled chain state only." in text
