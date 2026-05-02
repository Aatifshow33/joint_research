from __future__ import annotations

import json

from joint_research.research.wallet_flow_approval_execution_contract import (
    build_wallet_flow_approval_execution_contract,
    write_wallet_flow_approval_execution_contract,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _plan_payload(*, plan_status: str = "READY", rows: int = 2) -> dict:
    return {
        "plan_status": plan_status,
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


def _handoff_payload(*, handoff_status: str = "READY_FOR_MANUAL_APPROVAL", plan_status: str = "READY") -> dict:
    return {
        "handoff_status": handoff_status,
        "plan_status": plan_status,
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 2,
        "planned_row_count": 2,
        "planned_rows": _plan_payload(rows=2)["planned_rows"],
    }


def _ledger_payload(*, ledger_status: str = "PENDING_MANUAL_REVIEW", decision: str = "pending") -> dict:
    return {
        "ledger_status": ledger_status,
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "review note",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": 2,
        "planned_row_count": 2,
        "planned_rows": _plan_payload(rows=2)["planned_rows"],
    }


def test_approved_ledger_and_ready_chain_yields_contract_ready(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "CONTRACT_READY"


def test_pending_ledger_and_ready_handoff_yields_awaiting_approval(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="PENDING_MANUAL_REVIEW", decision="pending"))
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "AWAITING_APPROVAL"


def test_rejected_ledger_yields_rejected(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="REJECTED", decision="reject"))
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "REJECTED"


def test_missing_approval_ledger_yields_blocked(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=tmp_path / "missing-ledger.json",
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "BLOCKED"
    assert contract.ledger_status == "MISSING"


def test_invalid_approval_ledger_json_yields_blocked_with_warning(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    ledger_json.write_text("{not json")
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "BLOCKED"
    assert contract.ledger_status == "INVALID"
    assert any("approval_ledger_json_invalid" in warning for warning in contract.warnings)


def test_missing_handoff_yields_blocked(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=tmp_path / "missing-handoff.json",
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "BLOCKED"
    assert contract.handoff_status == "MISSING"


def test_missing_dry_run_plan_yields_blocked(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(handoff_json, _handoff_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=tmp_path / "missing-plan.json",
    )

    assert contract.contract_status == "BLOCKED"
    assert contract.plan_status == "MISSING"


def test_inconsistent_statuses_yield_blocked(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(handoff_json, _handoff_payload(plan_status="BLOCKED"))
    _write_json(plan_json, _plan_payload(plan_status="READY"))

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.contract_status == "BLOCKED"
    assert any(reason.startswith("inconsistent_status:") for reason in contract.block_reasons)


def test_contract_flags_lists_and_mode(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"
    _write_json(ledger_json, _ledger_payload(ledger_status="APPROVED", decision="approve"))
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload())

    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
    )

    assert contract.approval_required is True
    assert contract.manual_operator_only is True
    assert contract.no_execution is True
    assert contract.no_ingestion is True
    assert contract.live_adapter_enabled is False
    assert contract.execution_mode == "contract_only"
    assert contract.adapter_contract_version == "wallet_flow_execution_contract_v1"
    assert contract.allowed_future_adapter_actions == [
        "validate_contract",
        "load_manifest_row",
        "verify_idempotency_key",
        "verify_row_checksum",
        "emit_operator_preview",
    ]
    assert contract.forbidden_actions == [
        "shell_out",
        "network_request",
        "execute_manifest_command",
        "mutate_database",
        "place_order",
        "promote_candidate",
        "change_threshold",
        "enable_live_trading",
    ]


def test_first_ten_rows_include_command_and_contract_row_status_and_safety_copy(tmp_path) -> None:
    ledger_json = tmp_path / "ledger.json"
    handoff_json = tmp_path / "handoff.json"
    plan_json = tmp_path / "plan.json"

    rows = _plan_payload(rows=12)["planned_rows"]
    rows[0]["command_status"] = "APPROVED_FOR_REVIEW"
    rows[1]["command_status"] = "OTHER"
    ledger_payload = _ledger_payload(ledger_status="PENDING_MANUAL_REVIEW", decision="pending")
    ledger_payload["planned_rows"] = rows
    ledger_payload["planned_row_count"] = len(rows)
    _write_json(ledger_json, ledger_payload)
    _write_json(handoff_json, _handoff_payload())
    _write_json(plan_json, _plan_payload(rows=12))

    artifacts = write_wallet_flow_approval_execution_contract(
        approval_ledger_json=ledger_json,
        guarded_handoff_json=handoff_json,
        dry_run_plan_json=plan_json,
        output_dir=tmp_path / "out",
    )

    assert len(artifacts.contract.planned_rows) == 10
    assert artifacts.contract.planned_rows[0].contract_row_status == "CONTRACT_ROW_READY"
    assert artifacts.contract.planned_rows[1].contract_row_status == "BLOCKED"
    assert all(row.command.startswith("review_wallet_flow_backfill") for row in artifacts.contract.planned_rows)

    text = artifacts.contract_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Approval-to-execution contract only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Contract defines future adapter requirements only." in text
