from __future__ import annotations

import json

from joint_research.research.wallet_flow_disabled_adapter_run_receipt import (
    build_wallet_flow_disabled_adapter_run_receipt,
    write_wallet_flow_disabled_adapter_run_receipt,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _adapter_payload(*, adapter_status: str = "DISABLED_BY_POLICY", rows: int = 2) -> dict:
    decision = "approve" if adapter_status == "DISABLED_BY_POLICY" else "pending"
    if adapter_status == "REJECTED":
        decision = "reject"
    return {
        "adapter_status": adapter_status,
        "receipt_status": (
            "RECEIPT_READY"
            if adapter_status == "DISABLED_BY_POLICY"
            else "AWAITING_APPROVAL"
            if adapter_status == "AWAITING_APPROVAL"
            else "REJECTED"
            if adapter_status == "REJECTED"
            else "BLOCKED"
        ),
        "contract_status": (
            "CONTRACT_READY"
            if adapter_status == "DISABLED_BY_POLICY"
            else "AWAITING_APPROVAL"
            if adapter_status == "AWAITING_APPROVAL"
            else "REJECTED"
            if adapter_status == "REJECTED"
            else "BLOCKED"
        ),
        "ledger_status": (
            "APPROVED"
            if adapter_status == "DISABLED_BY_POLICY"
            else "PENDING_MANUAL_REVIEW"
            if adapter_status == "AWAITING_APPROVAL"
            else "REJECTED"
            if adapter_status == "REJECTED"
            else "BLOCKED"
        ),
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "phase 4.26",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
        "adapter_interface_version": "wallet_flow_disabled_adapter_interface_v1",
        "adapter_preview_rows": [
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
                    if adapter_status == "DISABLED_BY_POLICY"
                    else "RECEIPT_ROW_AWAITING_APPROVAL"
                    if adapter_status == "AWAITING_APPROVAL"
                    else "RECEIPT_ROW_REJECTED"
                    if adapter_status == "REJECTED"
                    else "BLOCKED"
                ),
                "adapter_row_status": (
                    "DISABLED_BY_POLICY"
                    if adapter_status == "DISABLED_BY_POLICY"
                    else "AWAITING_APPROVAL"
                    if adapter_status == "AWAITING_APPROVAL"
                    else "REJECTED"
                    if adapter_status == "REJECTED"
                    else "BLOCKED"
                ),
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def test_disabled_by_policy_adapter_yields_disabled_by_policy_confirmed(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    _write_json(adapter_json, _adapter_payload(adapter_status="DISABLED_BY_POLICY"))

    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json
    )
    assert receipt.run_status == "DISABLED_BY_POLICY_CONFIRMED"


def test_awaiting_approval_adapter_yields_awaiting_approval(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    _write_json(adapter_json, _adapter_payload(adapter_status="AWAITING_APPROVAL"))

    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json
    )
    assert receipt.run_status == "AWAITING_APPROVAL"


def test_rejected_adapter_yields_rejected(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    _write_json(adapter_json, _adapter_payload(adapter_status="REJECTED"))

    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json
    )
    assert receipt.run_status == "REJECTED"


def test_missing_adapter_json_yields_blocked(tmp_path) -> None:
    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=tmp_path / "missing.json"
    )
    assert receipt.run_status == "BLOCKED"
    assert receipt.adapter_status == "MISSING"


def test_invalid_adapter_json_yields_blocked_with_warning(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    adapter_json.write_text("{not json")

    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json
    )
    assert receipt.run_status == "BLOCKED"
    assert receipt.adapter_status == "INVALID"
    assert any("disabled_adapter_interface_json_invalid" in warning for warning in receipt.warnings)


def test_blocked_adapter_yields_blocked(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    _write_json(adapter_json, _adapter_payload(adapter_status="BLOCKED"))

    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json
    )
    assert receipt.run_status == "BLOCKED"


def test_flags_versions_confirmation_rows_and_safety_copy(tmp_path) -> None:
    adapter_json = tmp_path / "adapter.json"
    _write_json(adapter_json, _adapter_payload(adapter_status="DISABLED_BY_POLICY", rows=12))

    artifacts = write_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=adapter_json,
        output_dir=tmp_path / "out",
    )
    receipt = artifacts.receipt

    assert receipt.adapter_enabled is False
    assert receipt.execution_enabled is False
    assert receipt.network_enabled is False
    assert receipt.ingestion_enabled is False
    assert receipt.shell_enabled is False
    assert receipt.order_placement_enabled is False
    assert receipt.database_mutation_enabled is False

    assert receipt.approval_required is True
    assert receipt.manual_operator_only is True
    assert receipt.no_execution is True
    assert receipt.no_ingestion is True
    assert receipt.no_orders is True

    assert receipt.run_receipt_version == "wallet_flow_disabled_adapter_run_receipt_v1"
    assert receipt.execution_mode == "disabled_adapter_run_receipt_only"
    assert receipt.disabled_reason == "DISABLED_BY_POLICY"
    assert (
        receipt.confirmation_message
        == "Disabled adapter interface returned DISABLED_BY_POLICY; no execution was attempted."
    )

    assert len(receipt.run_rows) == 10
    assert all(
        row.command.startswith("review_wallet_flow_backfill")
        for row in receipt.run_rows
    )
    assert all(row.run_row_status == "DISABLED_BY_POLICY_CONFIRMED" for row in receipt.run_rows)

    text = artifacts.receipt_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Disabled adapter run receipt only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Adapter run is disabled by policy." in text
    assert "Run receipt records disabled result only." in text
