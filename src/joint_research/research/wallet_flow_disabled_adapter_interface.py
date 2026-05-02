"""Wallet-flow disabled adapter interface (hard disabled by policy).

This module defines a future adapter seam but keeps it permanently disabled.
It never executes commands, never shells out, never calls network, never
performs ingestion, and never places orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DISABLED_ADAPTER_INTERFACE_MD_FILENAME = "wallet_flow_disabled_adapter_interface.md"
DISABLED_ADAPTER_INTERFACE_JSON_FILENAME = "wallet_flow_disabled_adapter_interface.json"
DISABLED_REASON = "DISABLED_BY_POLICY"

ALLOWED_METHODS = [
    "validate_receipt",
    "summarize_disabled_preview",
    "emit_disabled_result",
]
FORBIDDEN_METHODS = [
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


@dataclass(frozen=True)
class WalletFlowDisabledAdapterPreviewRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    contract_row_status: str
    receipt_row_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    adapter_row_status: str


@dataclass(frozen=True)
class WalletFlowDisabledAdapterInterface:
    adapter_status: str
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
    adapter_interface_version: str
    execution_mode: str
    adapter_enabled: bool
    execution_enabled: bool
    network_enabled: bool
    ingestion_enabled: bool
    shell_enabled: bool
    order_placement_enabled: bool
    database_mutation_enabled: bool
    approval_required: bool
    manual_operator_only: bool
    no_execution: bool
    no_ingestion: bool
    no_orders: bool
    disabled_reason: str
    allowed_methods: list[str]
    forbidden_methods: list[str]
    block_reasons: list[str]
    warnings: list[str]
    adapter_preview_rows: list[WalletFlowDisabledAdapterPreviewRow]


@dataclass(frozen=True)
class WalletFlowDisabledAdapterInterfaceArtifacts:
    interface_md: Path
    interface_json: Path
    interface: WalletFlowDisabledAdapterInterface


def write_wallet_flow_disabled_adapter_interface(
    *,
    contract_audit_receipt_json: Path,
    output_dir: Path,
) -> WalletFlowDisabledAdapterInterfaceArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    interface = build_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=contract_audit_receipt_json
    )

    interface_md = output_dir / DISABLED_ADAPTER_INTERFACE_MD_FILENAME
    interface_json = output_dir / DISABLED_ADAPTER_INTERFACE_JSON_FILENAME
    interface_md.write_text(render_wallet_flow_disabled_adapter_interface(interface))
    interface_json.write_text(_stable_json(_interface_json_payload(interface)) + "\n")

    return WalletFlowDisabledAdapterInterfaceArtifacts(
        interface_md=interface_md,
        interface_json=interface_json,
        interface=interface,
    )


def build_wallet_flow_disabled_adapter_interface(
    *,
    contract_audit_receipt_json: Path,
) -> WalletFlowDisabledAdapterInterface:
    warnings: list[str] = []
    block_reasons: list[str] = []

    receipt_payload, receipt_state = _read_json_object(contract_audit_receipt_json)
    if receipt_state == "MISSING":
        receipt_status = "MISSING"
        block_reasons.append("contract_audit_receipt_missing")
    elif receipt_state == "INVALID":
        receipt_status = "INVALID"
        warnings.append(f"contract_audit_receipt_json_invalid path={contract_audit_receipt_json}")
        block_reasons.append("contract_audit_receipt_invalid")
    else:
        receipt_status = _payload_str(receipt_payload, "receipt_status", default="BLOCKED")

    contract_status = _payload_str(receipt_payload, "contract_status", default="unknown")
    ledger_status = _payload_str(receipt_payload, "ledger_status", default="unknown")
    decision = _payload_str(receipt_payload, "decision", default="unknown").lower()
    if decision not in {"pending", "approve", "reject"}:
        decision = "unknown"
    reviewer = _payload_str(receipt_payload, "reviewer", default="")
    review_note = _payload_str(receipt_payload, "review_note", default="")
    handoff_status = _payload_str(receipt_payload, "handoff_status", default="unknown")
    plan_status = _payload_str(receipt_payload, "plan_status", default="unknown")
    approved_packet_status = _payload_str(receipt_payload, "approved_packet_status", default="unknown")
    audit_status = _payload_str(receipt_payload, "audit_status", default="unknown")
    manifest_id = _payload_optional_str(receipt_payload, "manifest_id")
    manifest_rows = _payload_int(receipt_payload, "manifest_rows")
    planned_row_count = _payload_int(receipt_payload, "planned_row_count")

    if receipt_status == "RECEIPT_READY":
        adapter_status = "DISABLED_BY_POLICY"
    elif receipt_status == "AWAITING_APPROVAL":
        adapter_status = "AWAITING_APPROVAL"
    elif receipt_status == "REJECTED":
        adapter_status = "REJECTED"
    else:
        adapter_status = "BLOCKED"
        if receipt_status not in {"MISSING", "INVALID"}:
            block_reasons.append(f"receipt_status_{receipt_status.lower()}")

    preview_rows = _build_adapter_preview_rows(
        receipt_payload=receipt_payload,
        adapter_status=adapter_status,
        limit=10,
    )

    return WalletFlowDisabledAdapterInterface(
        adapter_status=adapter_status,
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
        adapter_interface_version="wallet_flow_disabled_adapter_interface_v1",
        execution_mode="disabled_adapter_interface_only",
        adapter_enabled=False,
        execution_enabled=False,
        network_enabled=False,
        ingestion_enabled=False,
        shell_enabled=False,
        order_placement_enabled=False,
        database_mutation_enabled=False,
        approval_required=True,
        manual_operator_only=True,
        no_execution=True,
        no_ingestion=True,
        no_orders=True,
        disabled_reason=DISABLED_REASON,
        allowed_methods=list(ALLOWED_METHODS),
        forbidden_methods=list(FORBIDDEN_METHODS),
        block_reasons=sorted(set(block_reasons)),
        warnings=warnings,
        adapter_preview_rows=preview_rows,
    )


def render_wallet_flow_disabled_adapter_interface(
    interface: WalletFlowDisabledAdapterInterface,
) -> str:
    lines = [
        "# Wallet Flow Disabled Adapter Interface",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Disabled adapter interface only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Adapter is disabled by policy.",
        "Adapter defines interface behavior only.",
        "",
        "## Adapter Status",
        "",
        f"- adapter_status: {interface.adapter_status}",
        f"- receipt_status: {interface.receipt_status}",
        f"- contract_status: {interface.contract_status}",
        f"- ledger_status: {interface.ledger_status}",
        f"- decision: {interface.decision}",
        f"- reviewer: {interface.reviewer or '(none)'}",
        f"- review_note: {interface.review_note or '(none)'}",
        f"- handoff_status: {interface.handoff_status}",
        f"- plan_status: {interface.plan_status}",
        f"- approved_packet_status: {interface.approved_packet_status}",
        f"- audit_status: {interface.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {interface.manifest_id or '(missing)'}",
        f"- manifest_rows: {interface.manifest_rows}",
        f"- planned_row_count: {interface.planned_row_count}",
        f"- adapter_interface_version: {interface.adapter_interface_version}",
        f"- execution_mode: {interface.execution_mode}",
        f"- adapter_enabled: {interface.adapter_enabled}",
        f"- execution_enabled: {interface.execution_enabled}",
        f"- network_enabled: {interface.network_enabled}",
        f"- ingestion_enabled: {interface.ingestion_enabled}",
        f"- shell_enabled: {interface.shell_enabled}",
        f"- order_placement_enabled: {interface.order_placement_enabled}",
        f"- database_mutation_enabled: {interface.database_mutation_enabled}",
        f"- approval_required: {interface.approval_required}",
        f"- manual_operator_only: {interface.manual_operator_only}",
        f"- no_execution: {interface.no_execution}",
        f"- no_ingestion: {interface.no_ingestion}",
        f"- no_orders: {interface.no_orders}",
        f"- disabled_reason: {interface.disabled_reason}",
        "",
        "## Allowed Methods",
        "",
    ]
    for method in interface.allowed_methods:
        lines.append(f"- {method}")

    lines.extend(["", "## Forbidden Methods", ""])
    for method in interface.forbidden_methods:
        lines.append(f"- {method}")

    lines.extend(["", "## Adapter Preview Rows (First 10)", ""])
    if not interface.adapter_preview_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | contract_row_status | receipt_row_status | idempotency_key | row_checksum | command | adapter_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|---|")
        for row in interface.adapter_preview_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.contract_row_status} | {row.receipt_row_status} | "
                f"{row.idempotency_key} | {row.row_checksum} | {row.command} | {row.adapter_row_status} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if interface.block_reasons:
        for reason in interface.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if interface.warnings:
        for warning in interface.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _build_adapter_preview_rows(
    *,
    receipt_payload: dict[str, object] | None,
    adapter_status: str,
    limit: int,
) -> list[WalletFlowDisabledAdapterPreviewRow]:
    rows_value = receipt_payload.get("receipt_rows") if receipt_payload else None
    if not isinstance(rows_value, list):
        return []

    if adapter_status == "DISABLED_BY_POLICY":
        row_status = "DISABLED_BY_POLICY"
    elif adapter_status == "AWAITING_APPROVAL":
        row_status = "AWAITING_APPROVAL"
    elif adapter_status == "REJECTED":
        row_status = "REJECTED"
    else:
        row_status = "BLOCKED"

    rows: list[WalletFlowDisabledAdapterPreviewRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowDisabledAdapterPreviewRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                contract_row_status=_to_str(row.get("contract_row_status")),
                receipt_row_status=_to_str(row.get("receipt_row_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                adapter_row_status=row_status,
            )
        )
    return rows


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


def _interface_json_payload(interface: WalletFlowDisabledAdapterInterface) -> dict[str, object]:
    return {
        "adapter_status": interface.adapter_status,
        "receipt_status": interface.receipt_status,
        "contract_status": interface.contract_status,
        "ledger_status": interface.ledger_status,
        "decision": interface.decision,
        "reviewer": interface.reviewer,
        "review_note": interface.review_note,
        "handoff_status": interface.handoff_status,
        "plan_status": interface.plan_status,
        "approved_packet_status": interface.approved_packet_status,
        "audit_status": interface.audit_status,
        "manifest_id": interface.manifest_id,
        "manifest_rows": interface.manifest_rows,
        "planned_row_count": interface.planned_row_count,
        "adapter_interface_version": interface.adapter_interface_version,
        "execution_mode": interface.execution_mode,
        "adapter_enabled": interface.adapter_enabled,
        "execution_enabled": interface.execution_enabled,
        "network_enabled": interface.network_enabled,
        "ingestion_enabled": interface.ingestion_enabled,
        "shell_enabled": interface.shell_enabled,
        "order_placement_enabled": interface.order_placement_enabled,
        "database_mutation_enabled": interface.database_mutation_enabled,
        "approval_required": interface.approval_required,
        "manual_operator_only": interface.manual_operator_only,
        "no_execution": interface.no_execution,
        "no_ingestion": interface.no_ingestion,
        "no_orders": interface.no_orders,
        "disabled_reason": interface.disabled_reason,
        "allowed_methods": interface.allowed_methods,
        "forbidden_methods": interface.forbidden_methods,
        "block_reasons": interface.block_reasons,
        "warnings": interface.warnings,
        "adapter_preview_rows": [asdict(row) for row in interface.adapter_preview_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "disabled_adapter_interface_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "adapter_disabled_by_policy": True,
            "adapter_defines_interface_behavior_only": True,
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
