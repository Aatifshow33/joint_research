from __future__ import annotations

import json

from joint_research.research.wallet_flow_disabled_adapter_interface import (
    build_wallet_flow_disabled_adapter_interface,
    write_wallet_flow_disabled_adapter_interface,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _receipt_payload(*, receipt_status: str = "RECEIPT_READY", rows: int = 2) -> dict:
    decision = "approve" if receipt_status == "RECEIPT_READY" else "pending"
    if receipt_status == "REJECTED":
        decision = "reject"
    return {
        "receipt_status": receipt_status,
        "contract_status": (
            "CONTRACT_READY"
            if receipt_status == "RECEIPT_READY"
            else "REJECTED"
            if receipt_status == "REJECTED"
            else "AWAITING_APPROVAL"
        ),
        "ledger_status": (
            "APPROVED"
            if receipt_status == "RECEIPT_READY"
            else "REJECTED"
            if receipt_status == "REJECTED"
            else "PENDING_MANUAL_REVIEW"
        ),
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "phase 4.25",
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
                "receipt_row_status": (
                    "RECEIPT_ROW_READY"
                    if receipt_status == "RECEIPT_READY"
                    else "RECEIPT_ROW_AWAITING_APPROVAL"
                    if receipt_status == "AWAITING_APPROVAL"
                    else "RECEIPT_ROW_REJECTED"
                    if receipt_status == "REJECTED"
                    else "BLOCKED"
                ),
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def test_receipt_ready_yields_disabled_by_policy(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    _write_json(receipt_json, _receipt_payload(receipt_status="RECEIPT_READY"))

    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json
    )
    assert interface.adapter_status == "DISABLED_BY_POLICY"


def test_awaiting_approval_receipt_yields_awaiting_approval(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    _write_json(receipt_json, _receipt_payload(receipt_status="AWAITING_APPROVAL"))

    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json
    )
    assert interface.adapter_status == "AWAITING_APPROVAL"


def test_rejected_receipt_yields_rejected(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    _write_json(receipt_json, _receipt_payload(receipt_status="REJECTED"))

    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json
    )
    assert interface.adapter_status == "REJECTED"


def test_missing_receipt_yields_blocked(tmp_path) -> None:
    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=tmp_path / "missing.json"
    )
    assert interface.adapter_status == "BLOCKED"
    assert interface.receipt_status == "MISSING"


def test_invalid_receipt_yields_blocked_with_warning(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text("{not json")

    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json
    )
    assert interface.adapter_status == "BLOCKED"
    assert interface.receipt_status == "INVALID"
    assert any("contract_audit_receipt_json_invalid" in warning for warning in interface.warnings)


def test_blocked_receipt_yields_blocked(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    _write_json(receipt_json, _receipt_payload(receipt_status="BLOCKED"))

    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json
    )
    assert interface.adapter_status == "BLOCKED"


def test_disabled_flags_methods_rows_and_safety_copy(tmp_path) -> None:
    receipt_json = tmp_path / "receipt.json"
    _write_json(receipt_json, _receipt_payload(receipt_status="RECEIPT_READY", rows=12))

    artifacts = write_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=receipt_json,
        output_dir=tmp_path / "out",
    )
    interface = artifacts.interface

    assert interface.adapter_enabled is False
    assert interface.execution_enabled is False
    assert interface.network_enabled is False
    assert interface.ingestion_enabled is False
    assert interface.shell_enabled is False
    assert interface.order_placement_enabled is False
    assert interface.database_mutation_enabled is False

    assert interface.approval_required is True
    assert interface.manual_operator_only is True
    assert interface.no_execution is True
    assert interface.no_ingestion is True
    assert interface.no_orders is True

    assert interface.adapter_interface_version == "wallet_flow_disabled_adapter_interface_v1"
    assert interface.execution_mode == "disabled_adapter_interface_only"
    assert interface.disabled_reason == "DISABLED_BY_POLICY"

    assert interface.allowed_methods == [
        "validate_receipt",
        "summarize_disabled_preview",
        "emit_disabled_result",
    ]
    assert interface.forbidden_methods == [
        "shell_out",
        "network_request",
        "execute_manifest_command",
        "mutate_database",
        "place_order",
        "promote_candidate",
        "change_threshold",
        "enable_live_trading",
        "enable_adapter",
        "transmit_order",
    ]

    assert len(interface.adapter_preview_rows) == 10
    assert all(
        row.command.startswith("review_wallet_flow_backfill")
        for row in interface.adapter_preview_rows
    )
    assert all(row.adapter_row_status == "DISABLED_BY_POLICY" for row in interface.adapter_preview_rows)

    text = artifacts.interface_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Disabled adapter interface only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Adapter is disabled by policy." in text
    assert "Adapter defines interface behavior only." in text
