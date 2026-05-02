"""Wallet-flow contract audit receipt artifact (receipt only).

This module verifies cross-artifact consistency without executing anything.
It never shells out, never executes manifest commands, never performs
ingestion, and never enables live execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONTRACT_AUDIT_RECEIPT_MD_FILENAME = "wallet_flow_contract_audit_receipt.md"
CONTRACT_AUDIT_RECEIPT_JSON_FILENAME = "wallet_flow_contract_audit_receipt.json"


@dataclass(frozen=True)
class WalletFlowContractAuditSourceArtifact:
    name: str
    path: str
    state: str
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True)
class WalletFlowContractAuditConsistencyCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class WalletFlowContractAuditReceiptRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    contract_row_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    receipt_row_status: str


@dataclass(frozen=True)
class WalletFlowContractAuditReceipt:
    receipt_status: str
    contract_status: str
    ledger_status: str
    decision: str
    reviewer: str
    review_note: str
    handoff_status: str
    plan_status: str
    approved_packet_status: str
    audit_status: str
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
    no_orders: bool
    source_artifacts: list[WalletFlowContractAuditSourceArtifact]
    consistency_checks: list[WalletFlowContractAuditConsistencyCheck]
    block_reasons: list[str]
    warnings: list[str]
    receipt_rows: list[WalletFlowContractAuditReceiptRow]


@dataclass(frozen=True)
class WalletFlowContractAuditReceiptArtifacts:
    receipt_md: Path
    receipt_json: Path
    receipt: WalletFlowContractAuditReceipt


def write_wallet_flow_contract_audit_receipt(
    *,
    approval_execution_contract_json: Path,
    approval_ledger_json: Path,
    guarded_handoff_json: Path,
    dry_run_plan_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
    output_dir: Path,
) -> WalletFlowContractAuditReceiptArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = build_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=approval_execution_contract_json,
        approval_ledger_json=approval_ledger_json,
        guarded_handoff_json=guarded_handoff_json,
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    receipt_md = output_dir / CONTRACT_AUDIT_RECEIPT_MD_FILENAME
    receipt_json = output_dir / CONTRACT_AUDIT_RECEIPT_JSON_FILENAME
    receipt_md.write_text(render_wallet_flow_contract_audit_receipt(receipt))
    receipt_json.write_text(_stable_json(_receipt_json_payload(receipt)) + "\n")

    return WalletFlowContractAuditReceiptArtifacts(
        receipt_md=receipt_md,
        receipt_json=receipt_json,
        receipt=receipt,
    )


def build_wallet_flow_contract_audit_receipt(
    *,
    approval_execution_contract_json: Path,
    approval_ledger_json: Path,
    guarded_handoff_json: Path,
    dry_run_plan_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
) -> WalletFlowContractAuditReceipt:
    warnings: list[str] = []
    block_reasons: list[str] = []

    contract_art = _load_json_artifact(
        name="approval_execution_contract_json",
        path=approval_execution_contract_json,
        warnings=warnings,
    )
    ledger_art = _load_json_artifact(
        name="approval_ledger_json",
        path=approval_ledger_json,
        warnings=warnings,
    )
    handoff_art = _load_json_artifact(
        name="guarded_handoff_json",
        path=guarded_handoff_json,
        warnings=warnings,
    )
    plan_art = _load_json_artifact(
        name="dry_run_plan_json",
        path=dry_run_plan_json,
        warnings=warnings,
    )
    approved_packet_art = _load_json_artifact(
        name="approved_packet_json",
        path=approved_packet_json,
        warnings=warnings,
    )
    audit_index_art = _load_json_artifact(
        name="audit_index_json",
        path=audit_index_json,
        warnings=warnings,
    )

    artifacts = [
        contract_art,
        ledger_art,
        handoff_art,
        plan_art,
        approved_packet_art,
        audit_index_art,
    ]
    source_artifacts = [
        WalletFlowContractAuditSourceArtifact(
            name=artifact["name"],
            path=artifact["path"],
            state=artifact["state"],
            size_bytes=artifact["size_bytes"],
            sha256=artifact["sha256"],
        )
        for artifact in artifacts
    ]

    for artifact in artifacts:
        if artifact["state"] == "MISSING":
            block_reasons.append(f"{artifact['name']}_missing")
        elif artifact["state"] == "INVALID":
            block_reasons.append(f"{artifact['name']}_invalid")

    contract_payload = contract_art["payload"]
    ledger_payload = ledger_art["payload"]
    handoff_payload = handoff_art["payload"]
    plan_payload = plan_art["payload"]
    approved_packet_payload = approved_packet_art["payload"]
    audit_index_payload = audit_index_art["payload"]

    contract_status = _status_from_payload(contract_payload, "contract_status", contract_art["state"])
    ledger_status = _status_from_payload(ledger_payload, "ledger_status", ledger_art["state"])
    decision = _decision_from_payload(contract_payload, ledger_payload)
    reviewer = _coalesce_str(
        _payload_str(contract_payload, "reviewer", default=""),
        _payload_str(ledger_payload, "reviewer", default=""),
    )
    review_note = _coalesce_str(
        _payload_str(contract_payload, "review_note", default=""),
        _payload_str(ledger_payload, "review_note", default=""),
    )
    handoff_status = _coalesce_status(
        _status_from_payload(handoff_payload, "handoff_status", handoff_art["state"]),
        _payload_str(contract_payload, "handoff_status", default="unknown"),
        _payload_str(ledger_payload, "handoff_status", default="unknown"),
    )
    plan_status = _coalesce_status(
        _status_from_payload(plan_payload, "plan_status", plan_art["state"]),
        _payload_str(contract_payload, "plan_status", default="unknown"),
        _payload_str(ledger_payload, "plan_status", default="unknown"),
        _payload_str(handoff_payload, "plan_status", default="unknown"),
    )
    approved_packet_status = _coalesce_status(
        _status_from_payload(approved_packet_payload, "export_status", approved_packet_art["state"], map_export=True),
        _payload_str(contract_payload, "approved_packet_status", default="unknown"),
        _payload_str(ledger_payload, "approved_packet_status", default="unknown"),
        _payload_str(handoff_payload, "approved_packet_status", default="unknown"),
        _payload_str(plan_payload, "approved_packet_status", default="unknown"),
    )
    audit_status = _coalesce_status(
        _status_from_payload(audit_index_payload, "audit_status", audit_index_art["state"]),
        _payload_str(contract_payload, "audit_status", default="unknown"),
        _payload_str(ledger_payload, "audit_status", default="unknown"),
        _payload_str(handoff_payload, "audit_status", default="unknown"),
        _payload_str(plan_payload, "audit_status", default="unknown"),
    )

    manifest_id_values = _collect_optional_strs(
        _payload_optional_str(contract_payload, "manifest_id"),
        _payload_optional_str(ledger_payload, "manifest_id"),
        _payload_optional_str(handoff_payload, "manifest_id"),
        _payload_optional_str(plan_payload, "manifest_id"),
        _payload_optional_str(approved_packet_payload, "manifest_id"),
    )
    manifest_rows_values = _collect_positive_ints(
        _payload_int(contract_payload, "manifest_rows"),
        _payload_int(ledger_payload, "manifest_rows"),
        _payload_int(handoff_payload, "manifest_rows"),
        _payload_int(plan_payload, "manifest_rows"),
        _payload_int(approved_packet_payload, "manifest_rows"),
        _payload_int(audit_index_payload, "manifest_rows"),
    )
    planned_row_count_values = _collect_positive_ints(
        _payload_int(contract_payload, "planned_row_count"),
        _payload_int(ledger_payload, "planned_row_count"),
        _payload_int(handoff_payload, "planned_row_count"),
        _payload_list_len(plan_payload, "planned_rows"),
    )

    manifest_id = manifest_id_values[0] if manifest_id_values else None
    manifest_rows = manifest_rows_values[0] if manifest_rows_values else 0
    planned_row_count = planned_row_count_values[0] if planned_row_count_values else 0

    consistency_checks = _build_consistency_checks(
        contract_payload=contract_payload,
        ledger_payload=ledger_payload,
        handoff_payload=handoff_payload,
        plan_payload=plan_payload,
        approved_packet_payload=approved_packet_payload,
        audit_index_payload=audit_index_payload,
        manifest_id_values=manifest_id_values,
        manifest_rows_values=manifest_rows_values,
        planned_row_count_values=planned_row_count_values,
    )
    for check in consistency_checks:
        if check.status == "FAIL":
            block_reasons.append(f"consistency_check_failed:{check.name}")

    if contract_status == "INVALID":
        block_reasons.append("contract_status_invalid")
    if ledger_status == "INVALID":
        block_reasons.append("ledger_status_invalid")
    if handoff_status == "unknown":
        block_reasons.append("handoff_status_unknown")
    if plan_status == "unknown":
        block_reasons.append("plan_status_unknown")
    if approved_packet_status == "unknown":
        block_reasons.append("approved_packet_status_unknown")
    if audit_status == "unknown":
        block_reasons.append("audit_status_unknown")

    adapter_contract_version = _payload_str(
        contract_payload, "adapter_contract_version", default=""
    )
    contract_execution_mode = _payload_str(contract_payload, "execution_mode", default="")
    contract_approval_required = _payload_bool(contract_payload, "approval_required")
    contract_manual_operator_only = _payload_bool(contract_payload, "manual_operator_only")
    contract_no_execution = _payload_bool(contract_payload, "no_execution")
    contract_no_ingestion = _payload_bool(contract_payload, "no_ingestion")
    contract_live_adapter_enabled = _payload_bool(contract_payload, "live_adapter_enabled")

    normalized_block_reasons = sorted(set(block_reasons))

    if normalized_block_reasons:
        receipt_status = "BLOCKED"
    elif (
        contract_status == "CONTRACT_READY"
        and ledger_status == "APPROVED"
        and decision == "approve"
        and handoff_status == "READY_FOR_MANUAL_APPROVAL"
        and plan_status == "READY"
        and approved_packet_status == "PASS"
        and audit_status == "READY"
        and contract_execution_mode == "contract_only"
        and adapter_contract_version == "wallet_flow_execution_contract_v1"
        and contract_approval_required is True
        and contract_manual_operator_only is True
        and contract_no_execution is True
        and contract_no_ingestion is True
        and contract_live_adapter_enabled is False
    ):
        receipt_status = "RECEIPT_READY"
    elif (
        contract_status == "AWAITING_APPROVAL"
        and ledger_status == "PENDING_MANUAL_REVIEW"
        and decision == "pending"
        and handoff_status == "READY_FOR_MANUAL_APPROVAL"
        and plan_status == "READY"
    ):
        receipt_status = "AWAITING_APPROVAL"
    elif (
        contract_status == "REJECTED"
        and ledger_status == "REJECTED"
        and decision == "reject"
    ):
        receipt_status = "REJECTED"
    else:
        receipt_status = "BLOCKED"
        if not normalized_block_reasons:
            normalized_block_reasons = ["receipt_status_conditions_not_met"]

    receipt_rows = _build_receipt_rows(
        contract_payload=contract_payload,
        receipt_status=receipt_status,
        limit=10,
    )

    return WalletFlowContractAuditReceipt(
        receipt_status=receipt_status,
        contract_status=contract_status,
        ledger_status=ledger_status,
        decision=decision,
        reviewer=reviewer,
        review_note=review_note,
        handoff_status=handoff_status,
        plan_status=plan_status,
        approved_packet_status=approved_packet_status,
        audit_status=audit_status,
        manifest_id=manifest_id,
        manifest_rows=manifest_rows,
        planned_row_count=planned_row_count,
        adapter_contract_version=adapter_contract_version,
        execution_mode="receipt_only",
        approval_required=True,
        manual_operator_only=True,
        no_execution=True,
        no_ingestion=True,
        live_adapter_enabled=False,
        no_orders=True,
        source_artifacts=source_artifacts,
        consistency_checks=consistency_checks,
        block_reasons=normalized_block_reasons,
        warnings=warnings,
        receipt_rows=receipt_rows,
    )


def render_wallet_flow_contract_audit_receipt(receipt: WalletFlowContractAuditReceipt) -> str:
    lines = [
        "# Wallet Flow Contract Audit Receipt",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Contract audit receipt only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Receipt records artifact consistency only.",
        "",
        "## Receipt Status",
        "",
        f"- receipt_status: {receipt.receipt_status}",
        f"- contract_status: {receipt.contract_status}",
        f"- ledger_status: {receipt.ledger_status}",
        f"- decision: {receipt.decision}",
        f"- reviewer: {receipt.reviewer or '(none)'}",
        f"- review_note: {receipt.review_note or '(none)'}",
        f"- handoff_status: {receipt.handoff_status}",
        f"- plan_status: {receipt.plan_status}",
        f"- approved_packet_status: {receipt.approved_packet_status}",
        f"- audit_status: {receipt.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {receipt.manifest_id or '(missing)'}",
        f"- manifest_rows: {receipt.manifest_rows}",
        f"- planned_row_count: {receipt.planned_row_count}",
        f"- adapter_contract_version: {receipt.adapter_contract_version or '(missing)'}",
        f"- execution_mode: {receipt.execution_mode}",
        f"- approval_required: {receipt.approval_required}",
        f"- manual_operator_only: {receipt.manual_operator_only}",
        f"- no_execution: {receipt.no_execution}",
        f"- no_ingestion: {receipt.no_ingestion}",
        f"- live_adapter_enabled: {receipt.live_adapter_enabled}",
        f"- no_orders: {receipt.no_orders}",
        "",
        "## Source Artifacts",
        "",
        "| name | path | state | size_bytes | sha256 |",
        "|---|---|---|---:|---|",
    ]
    for source in receipt.source_artifacts:
        lines.append(
            f"| {source.name} | {source.path} | {source.state} | "
            f"{source.size_bytes if source.size_bytes is not None else ''} | {source.sha256 or ''} |"
        )

    lines.extend(["", "## Consistency Checks", ""])
    lines.append("| name | status | detail |")
    lines.append("|---|---|---|")
    for check in receipt.consistency_checks:
        lines.append(f"| {check.name} | {check.status} | {check.detail} |")

    lines.extend(["", "## Receipt Rows (First 10)", ""])
    if not receipt.receipt_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | contract_row_status | idempotency_key | row_checksum | command | receipt_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|")
        for row in receipt.receipt_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.contract_row_status} | {row.idempotency_key} | "
                f"{row.row_checksum} | {row.command} | {row.receipt_row_status} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if receipt.block_reasons:
        for reason in receipt.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if receipt.warnings:
        for warning in receipt.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _build_consistency_checks(
    *,
    contract_payload: dict[str, object] | None,
    ledger_payload: dict[str, object] | None,
    handoff_payload: dict[str, object] | None,
    plan_payload: dict[str, object] | None,
    approved_packet_payload: dict[str, object] | None,
    audit_index_payload: dict[str, object] | None,
    manifest_id_values: list[str],
    manifest_rows_values: list[int],
    planned_row_count_values: list[int],
) -> list[WalletFlowContractAuditConsistencyCheck]:
    checks: list[WalletFlowContractAuditConsistencyCheck] = []

    checks.append(
        _consistency_multi_value_check(
            name="manifest_id_consistency",
            values=manifest_id_values,
        )
    )
    checks.append(
        _consistency_multi_value_check(
            name="manifest_rows_consistency",
            values=[str(value) for value in manifest_rows_values],
        )
    )
    checks.append(
        _consistency_multi_value_check(
            name="planned_row_count_consistency",
            values=[str(value) for value in planned_row_count_values],
        )
    )

    checks.append(
        _expected_value_check(
            name="contract_execution_mode",
            value=_payload_str(contract_payload, "execution_mode", default=""),
            expected="contract_only",
        )
    )
    checks.append(
        _expected_value_check(
            name="contract_adapter_contract_version",
            value=_payload_str(contract_payload, "adapter_contract_version", default=""),
            expected="wallet_flow_execution_contract_v1",
        )
    )
    checks.append(
        _expected_bool_check(
            name="contract_approval_required",
            value=_payload_bool(contract_payload, "approval_required"),
            expected=True,
        )
    )
    checks.append(
        _expected_bool_check(
            name="contract_manual_operator_only",
            value=_payload_bool(contract_payload, "manual_operator_only"),
            expected=True,
        )
    )
    checks.append(
        _expected_bool_check(
            name="contract_no_execution",
            value=_payload_bool(contract_payload, "no_execution"),
            expected=True,
        )
    )
    checks.append(
        _expected_bool_check(
            name="contract_no_ingestion",
            value=_payload_bool(contract_payload, "no_ingestion"),
            expected=True,
        )
    )
    checks.append(
        _expected_bool_check(
            name="contract_live_adapter_enabled",
            value=_payload_bool(contract_payload, "live_adapter_enabled"),
            expected=False,
        )
    )

    # Ensure top-level statuses are not contradictory when payloads are present.
    checks.append(
        _pairwise_status_check(
            name="ledger_vs_contract_status",
            left=_payload_str(ledger_payload, "ledger_status", default=""),
            right=_payload_str(contract_payload, "ledger_status", default=""),
        )
    )
    checks.append(
        _pairwise_status_check(
            name="handoff_vs_contract_status",
            left=_payload_str(handoff_payload, "handoff_status", default=""),
            right=_payload_str(contract_payload, "handoff_status", default=""),
        )
    )
    checks.append(
        _pairwise_status_check(
            name="plan_vs_contract_status",
            left=_payload_str(plan_payload, "plan_status", default=""),
            right=_payload_str(contract_payload, "plan_status", default=""),
        )
    )
    checks.append(
        _pairwise_status_check(
            name="approved_packet_vs_contract_status",
            left=_payload_str(approved_packet_payload, "export_status", default=""),
            right=_payload_str(contract_payload, "approved_packet_status", default=""),
            map_left_export=True,
        )
    )
    checks.append(
        _pairwise_status_check(
            name="audit_index_vs_contract_status",
            left=_payload_str(audit_index_payload, "audit_status", default=""),
            right=_payload_str(contract_payload, "audit_status", default=""),
        )
    )

    return checks


def _build_receipt_rows(
    *, contract_payload: dict[str, object] | None, receipt_status: str, limit: int
) -> list[WalletFlowContractAuditReceiptRow]:
    rows_value = contract_payload.get("planned_rows") if contract_payload else None
    if not isinstance(rows_value, list):
        return []

    rows: list[WalletFlowContractAuditReceiptRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break

        contract_row_status = _to_str(row.get("contract_row_status"))
        if receipt_status == "RECEIPT_READY" and contract_row_status == "CONTRACT_ROW_READY":
            receipt_row_status = "RECEIPT_ROW_READY"
        elif receipt_status == "AWAITING_APPROVAL":
            receipt_row_status = "RECEIPT_ROW_AWAITING_APPROVAL"
        elif receipt_status == "REJECTED":
            receipt_row_status = "RECEIPT_ROW_REJECTED"
        else:
            receipt_row_status = "BLOCKED"

        rows.append(
            WalletFlowContractAuditReceiptRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                contract_row_status=contract_row_status,
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                receipt_row_status=receipt_row_status,
            )
        )
    return rows


def _consistency_multi_value_check(
    *, name: str, values: list[str]
) -> WalletFlowContractAuditConsistencyCheck:
    unique_values = sorted(set(values))
    if len(unique_values) < 2:
        if unique_values:
            return WalletFlowContractAuditConsistencyCheck(
                name=name,
                status="PASS",
                detail=f"value={unique_values[0]}",
            )
        return WalletFlowContractAuditConsistencyCheck(
            name=name,
            status="SKIP",
            detail="insufficient_values",
        )
    return WalletFlowContractAuditConsistencyCheck(
        name=name,
        status="FAIL",
        detail=f"values={','.join(unique_values)}",
    )


def _expected_value_check(
    *, name: str, value: str, expected: str
) -> WalletFlowContractAuditConsistencyCheck:
    if not value:
        return WalletFlowContractAuditConsistencyCheck(
            name=name, status="SKIP", detail="value_missing"
        )
    if value == expected:
        return WalletFlowContractAuditConsistencyCheck(
            name=name, status="PASS", detail=f"value={value}"
        )
    return WalletFlowContractAuditConsistencyCheck(
        name=name, status="FAIL", detail=f"value={value} expected={expected}"
    )


def _expected_bool_check(
    *, name: str, value: bool | None, expected: bool
) -> WalletFlowContractAuditConsistencyCheck:
    if value is None:
        return WalletFlowContractAuditConsistencyCheck(
            name=name, status="SKIP", detail="value_missing"
        )
    if value == expected:
        return WalletFlowContractAuditConsistencyCheck(
            name=name, status="PASS", detail=f"value={value}"
        )
    return WalletFlowContractAuditConsistencyCheck(
        name=name, status="FAIL", detail=f"value={value} expected={expected}"
    )


def _pairwise_status_check(
    *,
    name: str,
    left: str,
    right: str,
    map_left_export: bool = False,
) -> WalletFlowContractAuditConsistencyCheck:
    if map_left_export:
        if left == "PASS":
            left = "PASS"
        elif left:
            left = "BLOCKED"

    if not left or not right:
        return WalletFlowContractAuditConsistencyCheck(
            name=name,
            status="SKIP",
            detail="value_missing",
        )
    if left == right:
        return WalletFlowContractAuditConsistencyCheck(
            name=name, status="PASS", detail=f"left={left} right={right}"
        )
    return WalletFlowContractAuditConsistencyCheck(
        name=name, status="FAIL", detail=f"left={left} right={right}"
    )


def _load_json_artifact(
    *,
    name: str,
    path: Path,
    warnings: list[str],
) -> dict[str, object]:
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "state": "MISSING",
            "size_bytes": None,
            "sha256": None,
            "payload": None,
        }

    data = path.read_bytes()
    size_bytes = len(data)
    sha256 = hashlib.sha256(data).hexdigest()
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        warnings.append(f"{name}_invalid_json path={path}")
        return {
            "name": name,
            "path": str(path),
            "state": "INVALID",
            "size_bytes": size_bytes,
            "sha256": sha256,
            "payload": None,
        }
    if not isinstance(payload, dict):
        warnings.append(f"{name}_invalid_json_object path={path}")
        return {
            "name": name,
            "path": str(path),
            "state": "INVALID",
            "size_bytes": size_bytes,
            "sha256": sha256,
            "payload": None,
        }
    return {
        "name": name,
        "path": str(path),
        "state": "OK",
        "size_bytes": size_bytes,
        "sha256": sha256,
        "payload": payload,
    }


def _receipt_json_payload(receipt: WalletFlowContractAuditReceipt) -> dict[str, object]:
    return {
        "receipt_status": receipt.receipt_status,
        "contract_status": receipt.contract_status,
        "ledger_status": receipt.ledger_status,
        "decision": receipt.decision,
        "reviewer": receipt.reviewer,
        "review_note": receipt.review_note,
        "handoff_status": receipt.handoff_status,
        "plan_status": receipt.plan_status,
        "approved_packet_status": receipt.approved_packet_status,
        "audit_status": receipt.audit_status,
        "manifest_id": receipt.manifest_id,
        "manifest_rows": receipt.manifest_rows,
        "planned_row_count": receipt.planned_row_count,
        "adapter_contract_version": receipt.adapter_contract_version,
        "execution_mode": receipt.execution_mode,
        "approval_required": receipt.approval_required,
        "manual_operator_only": receipt.manual_operator_only,
        "no_execution": receipt.no_execution,
        "no_ingestion": receipt.no_ingestion,
        "live_adapter_enabled": receipt.live_adapter_enabled,
        "no_orders": receipt.no_orders,
        "source_artifacts": [asdict(source) for source in receipt.source_artifacts],
        "consistency_checks": [asdict(check) for check in receipt.consistency_checks],
        "block_reasons": receipt.block_reasons,
        "warnings": receipt.warnings,
        "receipt_rows": [asdict(row) for row in receipt.receipt_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "contract_audit_receipt_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "receipt_records_artifact_consistency_only": True,
        },
    }


def _status_from_payload(
    payload: dict[str, object] | None,
    key: str,
    source_state: str,
    *,
    map_export: bool = False,
) -> str:
    if source_state in {"MISSING", "INVALID"}:
        return source_state
    value = _payload_str(payload, key, default="unknown")
    if not map_export:
        return value
    if value == "PASS":
        return "PASS"
    if value == "unknown":
        return "unknown"
    return "BLOCKED"


def _decision_from_payload(
    contract_payload: dict[str, object] | None,
    ledger_payload: dict[str, object] | None,
) -> str:
    decision = _payload_str(contract_payload, "decision", default="").lower()
    if decision in {"pending", "approve", "reject"}:
        return decision
    decision = _payload_str(ledger_payload, "decision", default="").lower()
    if decision in {"pending", "approve", "reject"}:
        return decision
    return "unknown"


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
    if isinstance(value, str) and value:
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


def _payload_bool(payload: dict[str, object] | None, key: str) -> bool | None:
    if payload is None:
        return None
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return None


def _collect_optional_strs(*values: str | None) -> list[str]:
    return [value for value in values if isinstance(value, str) and value]


def _collect_positive_ints(*values: int) -> list[int]:
    return [value for value in values if value > 0]


def _coalesce_status(*values: str) -> str:
    for value in values:
        if value != "unknown":
            return value
    return "unknown"


def _coalesce_str(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


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
