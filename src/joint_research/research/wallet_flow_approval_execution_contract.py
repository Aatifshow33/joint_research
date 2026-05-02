"""Wallet-flow approval-to-execution contract artifact (contract only).

This module is read-only and non-executing. It never shells out, never
executes manifest commands, never performs ingestion, and never enables a
live execution adapter.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

APPROVAL_EXECUTION_CONTRACT_MD_FILENAME = "wallet_flow_approval_execution_contract.md"
APPROVAL_EXECUTION_CONTRACT_JSON_FILENAME = "wallet_flow_approval_execution_contract.json"

_ROW_READY_COMMAND_STATUSES = {"REVIEW_READY", "APPROVED_FOR_REVIEW"}
_ALLOWED_FUTURE_ADAPTER_ACTIONS = [
    "validate_contract",
    "load_manifest_row",
    "verify_idempotency_key",
    "verify_row_checksum",
    "emit_operator_preview",
]
_FORBIDDEN_ACTIONS = [
    "shell_out",
    "network_request",
    "execute_manifest_command",
    "mutate_database",
    "place_order",
    "promote_candidate",
    "change_threshold",
    "enable_live_trading",
]


@dataclass(frozen=True)
class WalletFlowApprovalExecutionContractRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    contract_row_status: str


@dataclass(frozen=True)
class WalletFlowApprovalExecutionContract:
    contract_status: str
    ledger_status: str
    decision: str
    reviewer: str
    review_note: str
    handoff_status: str
    plan_status: str
    approved_packet_status: str
    audit_status: str
    block_reasons: list[str]
    warnings: list[str]
    manifest_id: str | None
    manifest_rows: int
    planned_row_count: int
    adapter_contract_version: str
    execution_mode: str
    approval_required: bool
    manual_operator_only: bool
    no_execution: bool
    no_ingestion: bool
    live_adapter_enabled: bool
    allowed_future_adapter_actions: list[str]
    forbidden_actions: list[str]
    planned_rows: list[WalletFlowApprovalExecutionContractRow]


@dataclass(frozen=True)
class WalletFlowApprovalExecutionContractArtifacts:
    contract_md: Path
    contract_json: Path
    contract: WalletFlowApprovalExecutionContract


def write_wallet_flow_approval_execution_contract(
    *,
    approval_ledger_json: Path,
    guarded_handoff_json: Path,
    dry_run_plan_json: Path,
    output_dir: Path,
) -> WalletFlowApprovalExecutionContractArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = build_wallet_flow_approval_execution_contract(
        approval_ledger_json=approval_ledger_json,
        guarded_handoff_json=guarded_handoff_json,
        dry_run_plan_json=dry_run_plan_json,
    )

    contract_md = output_dir / APPROVAL_EXECUTION_CONTRACT_MD_FILENAME
    contract_json = output_dir / APPROVAL_EXECUTION_CONTRACT_JSON_FILENAME
    contract_md.write_text(render_wallet_flow_approval_execution_contract(contract))
    contract_json.write_text(_stable_json(_contract_json_payload(contract)) + "\n")

    return WalletFlowApprovalExecutionContractArtifacts(
        contract_md=contract_md,
        contract_json=contract_json,
        contract=contract,
    )


def build_wallet_flow_approval_execution_contract(
    *,
    approval_ledger_json: Path,
    guarded_handoff_json: Path,
    dry_run_plan_json: Path,
) -> WalletFlowApprovalExecutionContract:
    warnings: list[str] = []
    block_reasons: list[str] = []

    ledger_payload, ledger_state = _read_json_object(approval_ledger_json)
    if ledger_state == "MISSING":
        ledger_status = "MISSING"
        decision = "unknown"
        reviewer = ""
        review_note = ""
        block_reasons.append("approval_ledger_missing")
    elif ledger_state == "INVALID":
        ledger_status = "INVALID"
        decision = "unknown"
        reviewer = ""
        review_note = ""
        warnings.append(f"approval_ledger_json_invalid path={approval_ledger_json}")
        block_reasons.append("approval_ledger_invalid")
    else:
        ledger_status = _payload_str(ledger_payload, "ledger_status", default="INVALID")
        decision_candidate = _payload_str(ledger_payload, "decision", default="unknown").lower()
        decision = decision_candidate if decision_candidate in {"pending", "approve", "reject"} else "unknown"
        reviewer = _payload_str(ledger_payload, "reviewer", default="")
        review_note = _payload_str(ledger_payload, "review_note", default="")
        if ledger_status == "INVALID":
            block_reasons.append("approval_ledger_missing_ledger_status")
        if decision == "unknown":
            block_reasons.append("approval_ledger_missing_or_invalid_decision")

    handoff_payload, handoff_state = _read_json_object(guarded_handoff_json)
    if handoff_state == "MISSING":
        handoff_status = "MISSING"
        block_reasons.append("guarded_handoff_missing")
    elif handoff_state == "INVALID":
        handoff_status = "INVALID"
        warnings.append(f"guarded_handoff_json_invalid path={guarded_handoff_json}")
        block_reasons.append("guarded_handoff_invalid")
    else:
        handoff_status = _payload_str(handoff_payload, "handoff_status", default="unknown")
        if handoff_status == "unknown":
            block_reasons.append("guarded_handoff_missing_handoff_status")

    plan_payload, plan_state = _read_json_object(dry_run_plan_json)
    if plan_state == "MISSING":
        plan_status = "MISSING"
        block_reasons.append("dry_run_plan_missing")
    elif plan_state == "INVALID":
        plan_status = "INVALID"
        warnings.append(f"dry_run_plan_json_invalid path={dry_run_plan_json}")
        block_reasons.append("dry_run_plan_invalid")
    else:
        plan_status = _payload_str(plan_payload, "plan_status", default="unknown")
        if plan_status == "unknown":
            block_reasons.append("dry_run_plan_missing_plan_status")

    # Prefer ledger's chain statuses; fall back to handoff then plan.
    approved_packet_status = _coalesce_status(
        _payload_str(ledger_payload, "approved_packet_status", default="unknown"),
        _payload_str(handoff_payload, "approved_packet_status", default="unknown"),
        _payload_str(plan_payload, "approved_packet_status", default="unknown"),
    )
    audit_status = _coalesce_status(
        _payload_str(ledger_payload, "audit_status", default="unknown"),
        _payload_str(handoff_payload, "audit_status", default="unknown"),
        _payload_str(plan_payload, "audit_status", default="unknown"),
    )

    if approved_packet_status == "unknown":
        block_reasons.append("approved_packet_status_unknown")
    if audit_status == "unknown":
        block_reasons.append("audit_status_unknown")

    _validate_consistency(
        ledger_payload=ledger_payload,
        handoff_payload=handoff_payload,
        plan_payload=plan_payload,
        block_reasons=block_reasons,
    )

    manifest_id = _coalesce_optional_str(
        _payload_optional_str(ledger_payload, "manifest_id"),
        _payload_optional_str(handoff_payload, "manifest_id"),
        _payload_optional_str(plan_payload, "manifest_id"),
    )
    manifest_rows = _coalesce_int(
        _payload_int(ledger_payload, "manifest_rows"),
        _payload_int(handoff_payload, "manifest_rows"),
        _payload_int(plan_payload, "manifest_rows"),
    )
    planned_row_count = _coalesce_int(
        _payload_int(ledger_payload, "planned_row_count"),
        _payload_int(handoff_payload, "planned_row_count"),
        _payload_list_len(plan_payload, "planned_rows"),
    )

    planned_rows = _extract_planned_rows(
        ledger_payload=ledger_payload,
        handoff_payload=handoff_payload,
        plan_payload=plan_payload,
        limit=10,
    )

    has_input_errors = any(
        reason.endswith("_missing") or reason.endswith("_invalid")
        for reason in block_reasons
    )

    normalized_block_reasons = sorted(set(block_reasons))
    if has_input_errors:
        contract_status = "BLOCKED"
    elif ledger_status == "REJECTED" and decision == "reject":
        contract_status = "REJECTED"
    elif (
        ledger_status == "APPROVED"
        and decision == "approve"
        and handoff_status == "READY_FOR_MANUAL_APPROVAL"
        and plan_status == "READY"
        and approved_packet_status == "PASS"
        and audit_status == "READY"
        and not normalized_block_reasons
    ):
        contract_status = "CONTRACT_READY"
    elif (
        ledger_status == "PENDING_MANUAL_REVIEW"
        and decision == "pending"
        and handoff_status == "READY_FOR_MANUAL_APPROVAL"
        and not normalized_block_reasons
    ):
        contract_status = "AWAITING_APPROVAL"
    else:
        contract_status = "BLOCKED"
        if not normalized_block_reasons:
            normalized_block_reasons = ["contract_status_conditions_not_met"]

    return WalletFlowApprovalExecutionContract(
        contract_status=contract_status,
        ledger_status=ledger_status,
        decision=decision,
        reviewer=reviewer,
        review_note=review_note,
        handoff_status=handoff_status,
        plan_status=plan_status,
        approved_packet_status=approved_packet_status,
        audit_status=audit_status,
        block_reasons=normalized_block_reasons,
        warnings=warnings,
        manifest_id=manifest_id,
        manifest_rows=manifest_rows,
        planned_row_count=planned_row_count,
        adapter_contract_version="wallet_flow_execution_contract_v1",
        execution_mode="contract_only",
        approval_required=True,
        manual_operator_only=True,
        no_execution=True,
        no_ingestion=True,
        live_adapter_enabled=False,
        allowed_future_adapter_actions=list(_ALLOWED_FUTURE_ADAPTER_ACTIONS),
        forbidden_actions=list(_FORBIDDEN_ACTIONS),
        planned_rows=planned_rows,
    )


def render_wallet_flow_approval_execution_contract(
    contract: WalletFlowApprovalExecutionContract,
) -> str:
    lines = [
        "# Wallet Flow Approval-To-Execution Contract",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Approval-to-execution contract only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Contract defines future adapter requirements only.",
        "",
        "## Contract Status",
        "",
        f"- contract_status: {contract.contract_status}",
        f"- ledger_status: {contract.ledger_status}",
        f"- decision: {contract.decision}",
        f"- reviewer: {contract.reviewer or '(none)'}",
        f"- review_note: {contract.review_note or '(none)'}",
        f"- handoff_status: {contract.handoff_status}",
        f"- plan_status: {contract.plan_status}",
        f"- approved_packet_status: {contract.approved_packet_status}",
        f"- audit_status: {contract.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {contract.manifest_id or '(missing)'}",
        f"- manifest_rows: {contract.manifest_rows}",
        f"- planned_row_count: {contract.planned_row_count}",
        f"- adapter_contract_version: {contract.adapter_contract_version}",
        f"- execution_mode: {contract.execution_mode}",
        f"- approval_required: {contract.approval_required}",
        f"- manual_operator_only: {contract.manual_operator_only}",
        f"- no_execution: {contract.no_execution}",
        f"- no_ingestion: {contract.no_ingestion}",
        f"- live_adapter_enabled: {contract.live_adapter_enabled}",
        "",
        "## Allowed Future Adapter Actions",
        "",
    ]
    for action in contract.allowed_future_adapter_actions:
        lines.append(f"- {action}")

    lines.extend(["", "## Forbidden Actions", ""])
    for action in contract.forbidden_actions:
        lines.append(f"- {action}")

    lines.extend(["", "## Planned Rows (First 10)", ""])
    if not contract.planned_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | idempotency_key | row_checksum | command | contract_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|")
        for row in contract.planned_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.idempotency_key} | {row.row_checksum} | {row.command} | "
                f"{row.contract_row_status} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if contract.block_reasons:
        for reason in contract.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if contract.warnings:
        for warning in contract.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _validate_consistency(
    *,
    ledger_payload: dict[str, object] | None,
    handoff_payload: dict[str, object] | None,
    plan_payload: dict[str, object] | None,
    block_reasons: list[str],
) -> None:
    _compare_status(
        block_reasons=block_reasons,
        left_name="ledger.handoff_status",
        left_value=_payload_str(ledger_payload, "handoff_status", default="unknown"),
        right_name="handoff.handoff_status",
        right_value=_payload_str(handoff_payload, "handoff_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="ledger.plan_status",
        left_value=_payload_str(ledger_payload, "plan_status", default="unknown"),
        right_name="plan.plan_status",
        right_value=_payload_str(plan_payload, "plan_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="ledger.approved_packet_status",
        left_value=_payload_str(ledger_payload, "approved_packet_status", default="unknown"),
        right_name="handoff.approved_packet_status",
        right_value=_payload_str(handoff_payload, "approved_packet_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="ledger.audit_status",
        left_value=_payload_str(ledger_payload, "audit_status", default="unknown"),
        right_name="handoff.audit_status",
        right_value=_payload_str(handoff_payload, "audit_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="handoff.plan_status",
        left_value=_payload_str(handoff_payload, "plan_status", default="unknown"),
        right_name="plan.plan_status",
        right_value=_payload_str(plan_payload, "plan_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="handoff.approved_packet_status",
        left_value=_payload_str(handoff_payload, "approved_packet_status", default="unknown"),
        right_name="plan.approved_packet_status",
        right_value=_payload_str(plan_payload, "approved_packet_status", default="unknown"),
    )
    _compare_status(
        block_reasons=block_reasons,
        left_name="handoff.audit_status",
        left_value=_payload_str(handoff_payload, "audit_status", default="unknown"),
        right_name="plan.audit_status",
        right_value=_payload_str(plan_payload, "audit_status", default="unknown"),
    )


def _compare_status(
    *,
    block_reasons: list[str],
    left_name: str,
    left_value: str,
    right_name: str,
    right_value: str,
) -> None:
    if left_value == "unknown" or right_value == "unknown":
        return
    if left_value != right_value:
        block_reasons.append(
            f"inconsistent_status:{left_name}={left_value}:{right_name}={right_value}"
        )


def _extract_planned_rows(
    *,
    ledger_payload: dict[str, object] | None,
    handoff_payload: dict[str, object] | None,
    plan_payload: dict[str, object] | None,
    limit: int,
) -> list[WalletFlowApprovalExecutionContractRow]:
    rows_value = _first_list(
        ledger_payload.get("planned_rows") if ledger_payload else None,
        handoff_payload.get("planned_rows") if handoff_payload else None,
        plan_payload.get("planned_rows") if plan_payload else None,
    )
    if rows_value is None:
        return []

    rows: list[WalletFlowApprovalExecutionContractRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        command_status = _to_str(row.get("command_status"))
        row_status = (
            "CONTRACT_ROW_READY"
            if command_status in _ROW_READY_COMMAND_STATUSES
            else "BLOCKED"
        )
        rows.append(
            WalletFlowApprovalExecutionContractRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=command_status,
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                contract_row_status=row_status,
            )
        )
    return rows


def _first_list(*values: object) -> list[object] | None:
    for value in values:
        if isinstance(value, list):
            return value
    return None


def _read_json_object(path: Path) -> tuple[dict[str, object] | None, str]:
    if not path.exists():
        return None, "MISSING"
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None, "INVALID"
    if not isinstance(payload, dict):
        return None, "INVALID"
    return payload, "OK"


def _contract_json_payload(contract: WalletFlowApprovalExecutionContract) -> dict[str, object]:
    return {
        "contract_status": contract.contract_status,
        "ledger_status": contract.ledger_status,
        "decision": contract.decision,
        "reviewer": contract.reviewer,
        "review_note": contract.review_note,
        "handoff_status": contract.handoff_status,
        "plan_status": contract.plan_status,
        "approved_packet_status": contract.approved_packet_status,
        "audit_status": contract.audit_status,
        "manifest_id": contract.manifest_id,
        "manifest_rows": contract.manifest_rows,
        "planned_row_count": contract.planned_row_count,
        "adapter_contract_version": contract.adapter_contract_version,
        "execution_mode": contract.execution_mode,
        "approval_required": contract.approval_required,
        "manual_operator_only": contract.manual_operator_only,
        "no_execution": contract.no_execution,
        "no_ingestion": contract.no_ingestion,
        "live_adapter_enabled": contract.live_adapter_enabled,
        "allowed_future_adapter_actions": contract.allowed_future_adapter_actions,
        "forbidden_actions": contract.forbidden_actions,
        "planned_rows": [asdict(row) for row in contract.planned_rows],
        "block_reasons": contract.block_reasons,
        "warnings": contract.warnings,
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "approval_to_execution_contract_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "contract_defines_future_adapter_requirements_only": True,
        },
    }


def _payload_str(payload: dict[str, object] | None, key: str, *, default: str) -> str:
    if payload is None:
        return default
    value = payload.get(key)
    if isinstance(value, str):
        return value
    return default


def _payload_optional_str(payload: dict[str, object] | None, key: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(key)
    if isinstance(value, str):
        return value
    return None


def _payload_int(payload: dict[str, object] | None, key: str) -> int:
    if payload is None:
        return 0
    value = payload.get(key)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _payload_list_len(payload: dict[str, object] | None, key: str) -> int:
    if payload is None:
        return 0
    value = payload.get(key)
    if isinstance(value, list):
        return len(value)
    return 0


def _coalesce_status(*values: str) -> str:
    for value in values:
        if value != "unknown":
            return value
    return "unknown"


def _coalesce_optional_str(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _coalesce_int(*values: int) -> int:
    for value in values:
        if value > 0:
            return value
    return 0


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _to_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
