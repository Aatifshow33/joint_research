from __future__ import annotations

import json

from joint_research.research.wallet_flow_contract_audit_receipt import (
    build_wallet_flow_contract_audit_receipt,
    write_wallet_flow_contract_audit_receipt,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _contract_payload(*, status: str = "AWAITING_APPROVAL", rows: int = 2) -> dict:
    decision = "approve" if status == "CONTRACT_READY" else "pending"
    ledger_status = "APPROVED" if status == "CONTRACT_READY" else "PENDING_MANUAL_REVIEW"
    return {
        "contract_status": status,
        "ledger_status": ledger_status,
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
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
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "contract_row_status": "CONTRACT_ROW_READY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _ledger_payload(*, ledger_status: str, decision: str, rows: int = 2) -> dict:
    return {
        "ledger_status": ledger_status,
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
    }


def _handoff_payload(*, rows: int = 2) -> dict:
    return {
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
    }


def _plan_payload(*, rows: int = 2) -> dict:
    return {
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _approved_packet_payload(*, rows: int = 2) -> dict:
    return {"export_status": "PASS", "manifest_rows": rows, "manifest_id": "mfest-1"}


def _audit_index_payload(*, rows: int = 2) -> dict:
    return {"audit_status": "READY", "manifest_rows": rows}


def _write_all(tmp_path, *, contract: dict, ledger: dict, handoff: dict, plan: dict, packet: dict, audit: dict):
    contract_json = tmp_path / "contract.json"
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    packet_json = tmp_path / "packet.json"
    audit_json = tmp_path / "audit.json"
    _write_json(contract_json, contract)
    _write_json(ledger_json, ledger)
    _write_json(handoff_json, handoff)
    _write_json(plan_json, plan)
    _write_json(packet_json, packet)
    _write_json(audit_json, audit)
    return contract_json, ledger_json, handoff_json, plan_json, packet_json, audit_json


def test_contract_ready_chain_yields_receipt_ready(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(status="CONTRACT_READY"),
        ledger=_ledger_payload(ledger_status="APPROVED", decision="approve"),
        handoff=_handoff_payload(),
        plan=_plan_payload(),
        packet=_approved_packet_payload(),
        audit=_audit_index_payload(),
    )

    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=paths[0],
        approval_ledger_json=paths[1],
        guarded_handoff_json=paths[2],
        dry_run_plan_json=paths[3],
        approved_packet_json=paths[4],
        audit_index_json=paths[5],
    )
    assert receipt.receipt_status == "RECEIPT_READY"


def test_awaiting_approval_chain_yields_awaiting_approval(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(status="AWAITING_APPROVAL"),
        ledger=_ledger_payload(ledger_status="PENDING_MANUAL_REVIEW", decision="pending"),
        handoff=_handoff_payload(),
        plan=_plan_payload(),
        packet=_approved_packet_payload(),
        audit=_audit_index_payload(),
    )

    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=paths[0],
        approval_ledger_json=paths[1],
        guarded_handoff_json=paths[2],
        dry_run_plan_json=paths[3],
        approved_packet_json=paths[4],
        audit_index_json=paths[5],
    )
    assert receipt.receipt_status == "AWAITING_APPROVAL"


def test_rejected_chain_yields_rejected(tmp_path) -> None:
    contract = _contract_payload(status="REJECTED")
    contract["decision"] = "reject"
    contract["ledger_status"] = "REJECTED"
    paths = _write_all(
        tmp_path,
        contract=contract,
        ledger=_ledger_payload(ledger_status="REJECTED", decision="reject"),
        handoff=_handoff_payload(),
        plan=_plan_payload(),
        packet=_approved_packet_payload(),
        audit=_audit_index_payload(),
    )

    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=paths[0],
        approval_ledger_json=paths[1],
        guarded_handoff_json=paths[2],
        dry_run_plan_json=paths[3],
        approved_packet_json=paths[4],
        audit_index_json=paths[5],
    )
    assert receipt.receipt_status == "REJECTED"


def test_missing_and_invalid_inputs_yield_blocked(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    packet_json = tmp_path / "packet.json"
    audit_json = tmp_path / "audit.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())
    _write_json(packet_json, _approved_packet_payload())
    audit_json.write_text("{not json")

    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=tmp_path / "missing-contract.json",
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
        approved_packet_json=packet_json,
        audit_index_json=audit_json,
    )
    assert receipt.receipt_status == "BLOCKED"
    assert receipt.contract_status == "MISSING"
    assert any("audit_index_json_invalid" in warning for warning in receipt.warnings)


def test_missing_each_required_input_yields_blocked(tmp_path) -> None:
    paths = _write_all(
        tmp_path,
        contract=_contract_payload(status="CONTRACT_READY"),
        ledger=_ledger_payload(ledger_status="APPROVED", decision="approve"),
        handoff=_handoff_payload(),
        plan=_plan_payload(),
        packet=_approved_packet_payload(),
        audit=_audit_index_payload(),
    )
    labels = [
        ("contract", 0),
        ("ledger", 1),
        ("handoff", 2),
        ("plan", 3),
        ("packet", 4),
        ("audit", 5),
    ]
    for _, idx in labels:
        args = list(paths)
        args[idx] = tmp_path / f"missing-{idx}.json"
        receipt = build_wallet_flow_contract_audit_receipt(
            approval_execution_contract_json=args[0],
            approval_ledger_json=args[1],
            guarded_handoff_json=args[2],
            dry_run_plan_json=args[3],
            approved_packet_json=args[4],
            audit_index_json=args[5],
        )
        assert receipt.receipt_status == "BLOCKED"


def test_inconsistent_manifest_id_rows_and_planned_count_yield_blocked(tmp_path) -> None:
    contract = _contract_payload(status="CONTRACT_READY", rows=2)
    ledger = _ledger_payload(ledger_status="APPROVED", decision="approve", rows=2)
    handoff = _handoff_payload(rows=2)
    plan = _plan_payload(rows=2)
    packet = _approved_packet_payload(rows=2)
    audit = _audit_index_payload(rows=2)
    ledger["manifest_id"] = "mfest-2"
    handoff["manifest_rows"] = 3
    plan["planned_rows"] = plan["planned_rows"] + [plan["planned_rows"][0]]
    paths = _write_all(
        tmp_path,
        contract=contract,
        ledger=ledger,
        handoff=handoff,
        plan=plan,
        packet=packet,
        audit=audit,
    )

    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=paths[0],
        approval_ledger_json=paths[1],
        guarded_handoff_json=paths[2],
        dry_run_plan_json=paths[3],
        approved_packet_json=paths[4],
        audit_index_json=paths[5],
    )
    assert receipt.receipt_status == "BLOCKED"
    failed = {check.name for check in receipt.consistency_checks if check.status == "FAIL"}
    assert "manifest_id_consistency" in failed
    assert "manifest_rows_consistency" in failed
    assert "planned_row_count_consistency" in failed


def test_receipt_includes_source_artifacts_and_flags_and_rows_and_safety_copy(tmp_path) -> None:
    contract = _contract_payload(status="CONTRACT_READY", rows=12)
    contract["planned_rows"][0]["contract_row_status"] = "CONTRACT_ROW_READY"
    contract["planned_rows"][1]["contract_row_status"] = "BLOCKED"
    paths = _write_all(
        tmp_path,
        contract=contract,
        ledger=_ledger_payload(ledger_status="APPROVED", decision="approve", rows=12),
        handoff=_handoff_payload(rows=12),
        plan=_plan_payload(rows=12),
        packet=_approved_packet_payload(rows=12),
        audit=_audit_index_payload(rows=12),
    )

    artifacts = write_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=paths[0],
        approval_ledger_json=paths[1],
        guarded_handoff_json=paths[2],
        dry_run_plan_json=paths[3],
        approved_packet_json=paths[4],
        audit_index_json=paths[5],
        output_dir=tmp_path / "out",
    )
    receipt = artifacts.receipt
    assert receipt.approval_required is True
    assert receipt.manual_operator_only is True
    assert receipt.no_execution is True
    assert receipt.no_ingestion is True
    assert receipt.live_adapter_enabled is False
    assert receipt.no_orders is True
    assert receipt.execution_mode == "receipt_only"
    assert len(receipt.source_artifacts) == 6
    assert all(source.state == "OK" for source in receipt.source_artifacts)
    assert all(source.size_bytes is not None for source in receipt.source_artifacts)
    assert all(source.sha256 is not None for source in receipt.source_artifacts)
    assert receipt.consistency_checks
    assert len(receipt.receipt_rows) == 10
    assert all(row.command.startswith("review_wallet_flow_backfill") for row in receipt.receipt_rows)
    assert receipt.receipt_rows[0].receipt_row_status == "RECEIPT_ROW_READY"

    text = artifacts.receipt_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Contract audit receipt only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Receipt records artifact consistency only." in text
