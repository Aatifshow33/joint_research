from __future__ import annotations

import json

from joint_research.research.wallet_flow_disabled_policy_guard import (
    build_wallet_flow_disabled_policy_guard,
    write_wallet_flow_disabled_policy_guard,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _chain_payload(*, chain_status: str = "DISABLED_CHAIN_CONFIRMED", rows: int = 2) -> dict:
    contract_status = "CONTRACT_READY"
    receipt_status = "RECEIPT_READY"
    adapter_status = "DISABLED_BY_POLICY"
    run_status = "DISABLED_BY_POLICY_CONFIRMED"
    ledger_status = "APPROVED"
    decision = "approve"

    if chain_status == "AWAITING_APPROVAL":
        contract_status = "AWAITING_APPROVAL"
        receipt_status = "AWAITING_APPROVAL"
        adapter_status = "AWAITING_APPROVAL"
        run_status = "AWAITING_APPROVAL"
        ledger_status = "PENDING_MANUAL_REVIEW"
        decision = "pending"
    elif chain_status == "REJECTED":
        contract_status = "REJECTED"
        receipt_status = "REJECTED"
        adapter_status = "REJECTED"
        run_status = "REJECTED"
        ledger_status = "REJECTED"
        decision = "reject"
    elif chain_status == "BLOCKED":
        contract_status = "BLOCKED"
        receipt_status = "BLOCKED"
        adapter_status = "BLOCKED"
        run_status = "BLOCKED"
        ledger_status = "BLOCKED"
        decision = "unknown"

    return {
        "chain_status": chain_status,
        "contract_status": contract_status,
        "receipt_status": receipt_status,
        "adapter_status": adapter_status,
        "run_status": run_status,
        "ledger_status": ledger_status,
        "decision": decision,
        "reviewer": "manual-operator",
        "review_note": "phase 4.28",
        "handoff_status": "READY_FOR_MANUAL_APPROVAL",
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
        "chain_summary_version": "wallet_flow_disabled_chain_summary_v1",
        "execution_mode": "disabled_chain_summary_only",
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
        "disabled_reason": "DISABLED_BY_POLICY",
        "final_confirmation": "Wallet-flow chain is disabled by policy; no execution was attempted.",
        "chain_rows": [
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
                "chain_row_status": "DISABLED_CHAIN_CONFIRMED",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def test_valid_disabled_chain_confirmed_yields_policy_guard_pass(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, _chain_payload())

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "POLICY_GUARD_PASS"


def test_awaiting_chain_yields_awaiting_approval(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, _chain_payload(chain_status="AWAITING_APPROVAL"))

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "AWAITING_APPROVAL"


def test_rejected_chain_yields_rejected(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, _chain_payload(chain_status="REJECTED"))

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "REJECTED"


def test_blocked_chain_yields_blocked(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, _chain_payload(chain_status="BLOCKED"))

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"


def test_missing_chain_json_yields_blocked(tmp_path) -> None:
    guard = build_wallet_flow_disabled_policy_guard(
        disabled_chain_summary_json=tmp_path / "missing.json"
    )
    assert guard.guard_status == "BLOCKED"
    assert guard.chain_status == "MISSING"


def test_invalid_chain_json_yields_blocked_with_warning(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    chain_json.write_text("{not json")

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    assert guard.chain_status == "INVALID"
    assert any("disabled_chain_summary_json_invalid" in warning for warning in guard.warnings)


def test_required_disabled_flag_true_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload["network_enabled"] = True
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "network_enabled_false" in failed


def test_required_safety_flag_false_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload["manual_operator_only"] = False
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "manual_operator_only_true" in failed


def test_wrong_disabled_reason_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload["disabled_reason"] = "NOT_DISABLED"
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "disabled_reason_policy" in failed


def test_missing_final_confirmation_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload.pop("final_confirmation")
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "final_confirmation_present" in failed


def test_wrong_chain_summary_version_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload["chain_summary_version"] = "wallet_flow_disabled_chain_summary_v2"
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "chain_summary_version_expected" in failed


def test_wrong_chain_execution_mode_yields_blocked(tmp_path) -> None:
    payload = _chain_payload()
    payload["execution_mode"] = "other_mode"
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, payload)

    guard = build_wallet_flow_disabled_policy_guard(disabled_chain_summary_json=chain_json)
    assert guard.guard_status == "BLOCKED"
    failed = {check.name for check in guard.policy_checks if check.status == "FAIL"}
    assert "chain_execution_mode_expected" in failed


def test_versions_checks_rows_and_safety_copy(tmp_path) -> None:
    chain_json = tmp_path / "chain.json"
    _write_json(chain_json, _chain_payload(rows=12))

    artifacts = write_wallet_flow_disabled_policy_guard(
        disabled_chain_summary_json=chain_json,
        output_dir=tmp_path / "out",
    )
    guard = artifacts.guard

    assert guard.policy_guard_version == "wallet_flow_disabled_policy_guard_v1"
    assert guard.execution_mode == "disabled_policy_guard_only"
    assert guard.guard_confirmation == (
        "Wallet-flow disabled policy guard passed; execution remains impossible by policy."
    )
    assert len(guard.policy_checks) >= 21
    assert len(guard.guard_rows) == 10
    assert all(
        row.command.startswith("review_wallet_flow_backfill") for row in guard.guard_rows
    )
    assert all(row.guard_row_status == "POLICY_GUARD_PASS" for row in guard.guard_rows)

    assert guard.adapter_enabled is False
    assert guard.execution_enabled is False
    assert guard.network_enabled is False
    assert guard.ingestion_enabled is False
    assert guard.shell_enabled is False
    assert guard.order_placement_enabled is False
    assert guard.database_mutation_enabled is False

    assert guard.approval_required is True
    assert guard.manual_operator_only is True
    assert guard.no_execution is True
    assert guard.no_ingestion is True
    assert guard.no_orders is True

    text = artifacts.guard_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Disabled policy guard only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "No orders placed." in text
    assert "Policy guard verifies disabled state only." in text
    assert "Execution remains disabled by policy." in text
