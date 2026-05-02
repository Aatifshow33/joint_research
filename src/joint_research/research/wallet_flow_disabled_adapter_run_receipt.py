"""Wallet-flow disabled adapter run receipt (disabled mode proof).

This module records that the disabled adapter interface was invoked in
disabled mode only. It never executes commands, never shells out, never uses
network, never performs ingestion, and never places orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DISABLED_ADAPTER_RUN_RECEIPT_MD_FILENAME = "wallet_flow_disabled_adapter_run_receipt.md"
DISABLED_ADAPTER_RUN_RECEIPT_JSON_FILENAME = "wallet_flow_disabled_adapter_run_receipt.json"
DISABLED_REASON = "DISABLED_BY_POLICY"
CONFIRMATION_MESSAGE = (
    "Disabled adapter interface returned DISABLED_BY_POLICY; no execution was attempted."
)


@dataclass(frozen=True)
class WalletFlowDisabledAdapterRunRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    contract_row_status: str
    receipt_row_status: str
    adapter_row_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    run_row_status: str


@dataclass(frozen=True)
class WalletFlowDisabledAdapterRunReceipt:
    run_status: str
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
    run_receipt_version: str
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
    confirmation_message: str
    block_reasons: list[str]
    warnings: list[str]
    run_rows: list[WalletFlowDisabledAdapterRunRow]


@dataclass(frozen=True)
class WalletFlowDisabledAdapterRunReceiptArtifacts:
    receipt_md: Path
    receipt_json: Path
    receipt: WalletFlowDisabledAdapterRunReceipt


def write_wallet_flow_disabled_adapter_run_receipt(
    *,
    disabled_adapter_interface_json: Path,
    output_dir: Path,
) -> WalletFlowDisabledAdapterRunReceiptArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = build_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=disabled_adapter_interface_json
    )

    receipt_md = output_dir / DISABLED_ADAPTER_RUN_RECEIPT_MD_FILENAME
    receipt_json = output_dir / DISABLED_ADAPTER_RUN_RECEIPT_JSON_FILENAME
    receipt_md.write_text(render_wallet_flow_disabled_adapter_run_receipt(receipt))
    receipt_json.write_text(_stable_json(_run_receipt_json_payload(receipt)) + "\n")

    return WalletFlowDisabledAdapterRunReceiptArtifacts(
        receipt_md=receipt_md,
        receipt_json=receipt_json,
        receipt=receipt,
    )


def build_wallet_flow_disabled_adapter_run_receipt(
    *,
    disabled_adapter_interface_json: Path,
) -> WalletFlowDisabledAdapterRunReceipt:
    warnings: list[str] = []
    block_reasons: list[str] = []

    payload, state = _read_json_object(disabled_adapter_interface_json)
    if state == "MISSING":
        adapter_status = "MISSING"
        block_reasons.append("disabled_adapter_interface_missing")
    elif state == "INVALID":
        adapter_status = "INVALID"
        warnings.append(
            f"disabled_adapter_interface_json_invalid path={disabled_adapter_interface_json}"
        )
        block_reasons.append("disabled_adapter_interface_invalid")
    else:
        adapter_status = _payload_str(payload, "adapter_status", default="BLOCKED")

    receipt_status = _payload_str(payload, "receipt_status", default="unknown")
    contract_status = _payload_str(payload, "contract_status", default="unknown")
    ledger_status = _payload_str(payload, "ledger_status", default="unknown")
    decision = _payload_str(payload, "decision", default="unknown").lower()
    if decision not in {"pending", "approve", "reject"}:
        decision = "unknown"
    reviewer = _payload_str(payload, "reviewer", default="")
    review_note = _payload_str(payload, "review_note", default="")
    handoff_status = _payload_str(payload, "handoff_status", default="unknown")
    plan_status = _payload_str(payload, "plan_status", default="unknown")
    approved_packet_status = _payload_str(payload, "approved_packet_status", default="unknown")
    audit_status = _payload_str(payload, "audit_status", default="unknown")
    manifest_id = _payload_optional_str(payload, "manifest_id")
    manifest_rows = _payload_int(payload, "manifest_rows")
    planned_row_count = _payload_int(payload, "planned_row_count")
    adapter_interface_version = _payload_str(payload, "adapter_interface_version", default="")

    if adapter_status == "DISABLED_BY_POLICY":
        run_status = "DISABLED_BY_POLICY_CONFIRMED"
    elif adapter_status == "AWAITING_APPROVAL":
        run_status = "AWAITING_APPROVAL"
    elif adapter_status == "REJECTED":
        run_status = "REJECTED"
    else:
        run_status = "BLOCKED"
        if adapter_status not in {"MISSING", "INVALID"}:
            block_reasons.append(f"adapter_status_{adapter_status.lower()}")

    run_rows = _build_run_rows(payload=payload, run_status=run_status, limit=10)

    return WalletFlowDisabledAdapterRunReceipt(
        run_status=run_status,
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
        adapter_interface_version=adapter_interface_version,
        run_receipt_version="wallet_flow_disabled_adapter_run_receipt_v1",
        execution_mode="disabled_adapter_run_receipt_only",
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
        confirmation_message=CONFIRMATION_MESSAGE,
        block_reasons=sorted(set(block_reasons)),
        warnings=warnings,
        run_rows=run_rows,
    )


def render_wallet_flow_disabled_adapter_run_receipt(
    receipt: WalletFlowDisabledAdapterRunReceipt,
) -> str:
    lines = [
        "# Wallet Flow Disabled Adapter Run Receipt",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Disabled adapter run receipt only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Adapter run is disabled by policy.",
        "Run receipt records disabled result only.",
        "",
        "## Run Status",
        "",
        f"- run_status: {receipt.run_status}",
        f"- adapter_status: {receipt.adapter_status}",
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
        f"- adapter_interface_version: {receipt.adapter_interface_version or '(missing)'}",
        f"- run_receipt_version: {receipt.run_receipt_version}",
        f"- execution_mode: {receipt.execution_mode}",
        f"- adapter_enabled: {receipt.adapter_enabled}",
        f"- execution_enabled: {receipt.execution_enabled}",
        f"- network_enabled: {receipt.network_enabled}",
        f"- ingestion_enabled: {receipt.ingestion_enabled}",
        f"- shell_enabled: {receipt.shell_enabled}",
        f"- order_placement_enabled: {receipt.order_placement_enabled}",
        f"- database_mutation_enabled: {receipt.database_mutation_enabled}",
        f"- approval_required: {receipt.approval_required}",
        f"- manual_operator_only: {receipt.manual_operator_only}",
        f"- no_execution: {receipt.no_execution}",
        f"- no_ingestion: {receipt.no_ingestion}",
        f"- no_orders: {receipt.no_orders}",
        f"- disabled_reason: {receipt.disabled_reason}",
        f"- confirmation_message: {receipt.confirmation_message}",
        "",
        "## Run Rows (First 10)",
        "",
    ]

    if not receipt.run_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | contract_row_status | receipt_row_status | adapter_row_status | idempotency_key | row_checksum | command | run_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|---|---|")
        for row in receipt.run_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.contract_row_status} | {row.receipt_row_status} | "
                f"{row.adapter_row_status} | {row.idempotency_key} | {row.row_checksum} | {row.command} | "
                f"{row.run_row_status} |"
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


def _build_run_rows(
    *, payload: dict[str, object] | None, run_status: str, limit: int
) -> list[WalletFlowDisabledAdapterRunRow]:
    rows_value = payload.get("adapter_preview_rows") if payload else None
    if not isinstance(rows_value, list):
        return []

    if run_status == "DISABLED_BY_POLICY_CONFIRMED":
        row_status = "DISABLED_BY_POLICY_CONFIRMED"
    elif run_status == "AWAITING_APPROVAL":
        row_status = "AWAITING_APPROVAL"
    elif run_status == "REJECTED":
        row_status = "REJECTED"
    else:
        row_status = "BLOCKED"

    rows: list[WalletFlowDisabledAdapterRunRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowDisabledAdapterRunRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                contract_row_status=_to_str(row.get("contract_row_status")),
                receipt_row_status=_to_str(row.get("receipt_row_status")),
                adapter_row_status=_to_str(row.get("adapter_row_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                run_row_status=row_status,
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


def _run_receipt_json_payload(receipt: WalletFlowDisabledAdapterRunReceipt) -> dict[str, object]:
    return {
        "run_status": receipt.run_status,
        "adapter_status": receipt.adapter_status,
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
        "adapter_interface_version": receipt.adapter_interface_version,
        "run_receipt_version": receipt.run_receipt_version,
        "execution_mode": receipt.execution_mode,
        "adapter_enabled": receipt.adapter_enabled,
        "execution_enabled": receipt.execution_enabled,
        "network_enabled": receipt.network_enabled,
        "ingestion_enabled": receipt.ingestion_enabled,
        "shell_enabled": receipt.shell_enabled,
        "order_placement_enabled": receipt.order_placement_enabled,
        "database_mutation_enabled": receipt.database_mutation_enabled,
        "approval_required": receipt.approval_required,
        "manual_operator_only": receipt.manual_operator_only,
        "no_execution": receipt.no_execution,
        "no_ingestion": receipt.no_ingestion,
        "no_orders": receipt.no_orders,
        "disabled_reason": receipt.disabled_reason,
        "confirmation_message": receipt.confirmation_message,
        "block_reasons": receipt.block_reasons,
        "warnings": receipt.warnings,
        "run_rows": [asdict(row) for row in receipt.run_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "disabled_adapter_run_receipt_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "adapter_run_disabled_by_policy": True,
            "run_receipt_records_disabled_result_only": True,
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
