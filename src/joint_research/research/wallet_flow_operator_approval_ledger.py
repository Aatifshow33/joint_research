"""Wallet-flow operator approval ledger (local manual decision record only).

This module is non-executing: it never shells out, never executes manifest
commands, and never performs ingestion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

OPERATOR_APPROVAL_LEDGER_MD_FILENAME = "wallet_flow_operator_approval_ledger.md"
OPERATOR_APPROVAL_LEDGER_JSON_FILENAME = "wallet_flow_operator_approval_ledger.json"

_VALID_DECISIONS = {"pending", "approve", "reject"}


@dataclass(frozen=True)
class WalletFlowOperatorApprovalLedgerRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    idempotency_key: str
    row_checksum: str
    command: str


@dataclass(frozen=True)
class WalletFlowOperatorApprovalLedger:
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
    batch_count: int
    command_status_counts: list[tuple[str, int]]
    approval_required: bool
    manual_operator_only: bool
    no_execution: bool
    execution_mode: str
    planned_rows: list[WalletFlowOperatorApprovalLedgerRow]


@dataclass(frozen=True)
class WalletFlowOperatorApprovalLedgerArtifacts:
    ledger_md: Path
    ledger_json: Path
    ledger: WalletFlowOperatorApprovalLedger


def write_wallet_flow_operator_approval_ledger(
    *,
    guarded_handoff_json: Path,
    decision: str,
    reviewer: str,
    review_note: str,
    output_dir: Path,
) -> WalletFlowOperatorApprovalLedgerArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=guarded_handoff_json,
        decision=decision,
        reviewer=reviewer,
        review_note=review_note,
    )

    ledger_md = output_dir / OPERATOR_APPROVAL_LEDGER_MD_FILENAME
    ledger_json = output_dir / OPERATOR_APPROVAL_LEDGER_JSON_FILENAME
    ledger_md.write_text(render_wallet_flow_operator_approval_ledger(ledger))
    ledger_json.write_text(_stable_json(_ledger_json_payload(ledger)) + "\n")

    return WalletFlowOperatorApprovalLedgerArtifacts(
        ledger_md=ledger_md,
        ledger_json=ledger_json,
        ledger=ledger,
    )


def build_wallet_flow_operator_approval_ledger(
    *,
    guarded_handoff_json: Path,
    decision: str,
    reviewer: str,
    review_note: str,
) -> WalletFlowOperatorApprovalLedger:
    normalized_decision = decision.strip().lower()
    if normalized_decision not in _VALID_DECISIONS:
        raise ValueError(
            "decision must be one of: pending, approve, reject"
        )

    warnings: list[str] = []
    block_reasons: list[str] = []

    payload, state = _read_json_object(guarded_handoff_json)
    if state == "MISSING":
        handoff_status = "MISSING"
        block_reasons.append("guarded_handoff_missing")
    elif state == "INVALID":
        handoff_status = "INVALID"
        warnings.append(f"guarded_handoff_json_invalid path={guarded_handoff_json}")
        block_reasons.append("guarded_handoff_invalid")
    else:
        handoff_value = payload.get("handoff_status") if payload else None
        if isinstance(handoff_value, str):
            if handoff_value == "READY_FOR_MANUAL_APPROVAL":
                handoff_status = "READY_FOR_MANUAL_APPROVAL"
            else:
                handoff_status = "BLOCKED"
                block_reasons.append(f"handoff_status_{handoff_value.lower()}")
        else:
            handoff_status = "INVALID"
            warnings.append("guarded_handoff_json_missing_handoff_status")
            block_reasons.append("guarded_handoff_invalid")

    plan_status = _payload_str(payload, "plan_status", default="INVALID")
    approved_packet_status = _payload_str(payload, "approved_packet_status", default="INVALID")
    audit_status = _payload_str(payload, "audit_status", default="INVALID")
    manifest_id = _payload_optional_str(payload, "manifest_id")
    manifest_rows = _payload_int(payload, "manifest_rows")
    planned_row_count = _payload_int(payload, "planned_row_count")
    batch_count = _payload_int(payload, "batch_count")
    command_status_counts = _parse_command_status_counts(
        payload.get("command_status_counts") if payload else None
    )
    planned_rows = _parse_planned_rows(payload.get("planned_rows") if payload else None, limit=10)

    if handoff_status != "READY_FOR_MANUAL_APPROVAL":
        block_reasons.append(f"handoff_status_not_ready:{handoff_status}")

    normalized_block_reasons = sorted(set(block_reasons))
    if normalized_block_reasons:
        ledger_status = "BLOCKED"
    elif normalized_decision == "approve":
        ledger_status = "APPROVED"
    elif normalized_decision == "reject":
        ledger_status = "REJECTED"
    else:
        ledger_status = "PENDING_MANUAL_REVIEW"

    return WalletFlowOperatorApprovalLedger(
        ledger_status=ledger_status,
        decision=normalized_decision,
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
        batch_count=batch_count,
        command_status_counts=command_status_counts,
        approval_required=True,
        manual_operator_only=True,
        no_execution=True,
        execution_mode="approval_ledger_only",
        planned_rows=planned_rows,
    )


def render_wallet_flow_operator_approval_ledger(
    ledger: WalletFlowOperatorApprovalLedger,
) -> str:
    lines = [
        "# Wallet Flow Operator Approval Ledger",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Operator approval ledger only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "Ledger records review decision only.",
        "",
        "## Ledger Status",
        "",
        f"- ledger_status: {ledger.ledger_status}",
        f"- decision: {ledger.decision}",
        f"- reviewer: {ledger.reviewer or '(none)'}",
        f"- review_note: {ledger.review_note or '(none)'}",
        f"- handoff_status: {ledger.handoff_status}",
        "",
        "## Chain Status",
        "",
        f"- plan_status: {ledger.plan_status}",
        f"- approved_packet_status: {ledger.approved_packet_status}",
        f"- audit_status: {ledger.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {ledger.manifest_id or '(missing)'}",
        f"- manifest_rows: {ledger.manifest_rows}",
        f"- planned_row_count: {ledger.planned_row_count}",
        f"- batch_count: {ledger.batch_count}",
        f"- approval_required: {ledger.approval_required}",
        f"- manual_operator_only: {ledger.manual_operator_only}",
        f"- no_execution: {ledger.no_execution}",
        f"- execution_mode: {ledger.execution_mode}",
        "",
        "## Command Status Counts",
        "",
    ]
    if ledger.command_status_counts:
        for status, count in ledger.command_status_counts:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Planned Rows (First 10)", ""])
    if not ledger.planned_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | idempotency_key | row_checksum | command |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|")
        for row in ledger.planned_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.idempotency_key} | {row.row_checksum} | {row.command} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if ledger.block_reasons:
        for reason in ledger.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if ledger.warnings:
        for warning in ledger.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


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


def _parse_command_status_counts(value: object) -> list[tuple[str, int]]:
    if not isinstance(value, list):
        return []
    pairs: list[tuple[str, int]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        status = row.get("command_status")
        count = row.get("count")
        if not isinstance(status, str):
            continue
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            continue
        pairs.append((status, count_int))
    return sorted(pairs, key=lambda item: item[0])


def _parse_planned_rows(
    value: object, *, limit: int
) -> list[WalletFlowOperatorApprovalLedgerRow]:
    if not isinstance(value, list):
        return []
    rows: list[WalletFlowOperatorApprovalLedgerRow] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowOperatorApprovalLedgerRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
            )
        )
    return rows


def _ledger_json_payload(ledger: WalletFlowOperatorApprovalLedger) -> dict[str, object]:
    return {
        "ledger_status": ledger.ledger_status,
        "decision": ledger.decision,
        "reviewer": ledger.reviewer,
        "review_note": ledger.review_note,
        "handoff_status": ledger.handoff_status,
        "plan_status": ledger.plan_status,
        "approved_packet_status": ledger.approved_packet_status,
        "audit_status": ledger.audit_status,
        "block_reasons": ledger.block_reasons,
        "warnings": ledger.warnings,
        "manifest_id": ledger.manifest_id,
        "manifest_rows": ledger.manifest_rows,
        "planned_row_count": ledger.planned_row_count,
        "batch_count": ledger.batch_count,
        "command_status_counts": [
            {"command_status": status, "count": count}
            for status, count in ledger.command_status_counts
        ],
        "approval_required": ledger.approval_required,
        "manual_operator_only": ledger.manual_operator_only,
        "no_execution": ledger.no_execution,
        "execution_mode": ledger.execution_mode,
        "planned_rows": [asdict(row) for row in ledger.planned_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "operator_approval_ledger_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "ledger_records_review_decision_only": True,
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
