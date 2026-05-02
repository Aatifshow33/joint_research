"""Wallet-flow guarded operator handoff (manual approval boundary).

This module is preview-only: it never executes commands, never shells out,
never performs ingestion, and never modifies source data.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

GUARDED_HANDOFF_MD_FILENAME = "wallet_flow_guarded_operator_handoff.md"
GUARDED_HANDOFF_JSON_FILENAME = "wallet_flow_guarded_operator_handoff.json"


@dataclass(frozen=True)
class WalletFlowGuardedHandoffRow:
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
class WalletFlowGuardedOperatorHandoff:
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
    planned_rows: list[WalletFlowGuardedHandoffRow]


@dataclass(frozen=True)
class WalletFlowGuardedOperatorHandoffArtifacts:
    handoff_md: Path
    handoff_json: Path
    handoff: WalletFlowGuardedOperatorHandoff


def write_wallet_flow_guarded_operator_handoff(
    *,
    dry_run_plan_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
    output_dir: Path,
) -> WalletFlowGuardedOperatorHandoffArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    handoff_md = output_dir / GUARDED_HANDOFF_MD_FILENAME
    handoff_json = output_dir / GUARDED_HANDOFF_JSON_FILENAME
    handoff_md.write_text(render_wallet_flow_guarded_operator_handoff(handoff))
    handoff_json.write_text(_stable_json(_handoff_json_payload(handoff)) + "\n")

    return WalletFlowGuardedOperatorHandoffArtifacts(
        handoff_md=handoff_md,
        handoff_json=handoff_json,
        handoff=handoff,
    )


def build_wallet_flow_guarded_operator_handoff(
    *,
    dry_run_plan_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
) -> WalletFlowGuardedOperatorHandoff:
    warnings: list[str] = []
    block_reasons: list[str] = []

    plan_payload, plan_state = _read_json_object(dry_run_plan_json)
    if plan_state == "MISSING":
        plan_status = "MISSING"
        block_reasons.append("dry_run_plan_missing")
    elif plan_state == "INVALID":
        plan_status = "INVALID"
        warnings.append(f"dry_run_plan_json_invalid path={dry_run_plan_json}")
        block_reasons.append("dry_run_plan_invalid")
    else:
        value = plan_payload.get("plan_status") if plan_payload else None
        if isinstance(value, str) and value == "READY":
            plan_status = "READY"
        elif isinstance(value, str):
            plan_status = "BLOCKED"
            block_reasons.append(f"dry_run_plan_status_{value.lower()}")
        else:
            plan_status = "INVALID"
            warnings.append("dry_run_plan_json_missing_plan_status")
            block_reasons.append("dry_run_plan_invalid")

    approved_payload, approved_state = _read_json_object(approved_packet_json)
    if approved_state == "MISSING":
        approved_packet_status = "MISSING"
        block_reasons.append("approved_packet_missing")
    elif approved_state == "INVALID":
        approved_packet_status = "INVALID"
        warnings.append(f"approved_packet_json_invalid path={approved_packet_json}")
        block_reasons.append("approved_packet_invalid")
    else:
        export_value = approved_payload.get("export_status") if approved_payload else None
        if isinstance(export_value, str) and export_value == "PASS":
            approved_packet_status = "PASS"
        elif isinstance(export_value, str):
            approved_packet_status = "BLOCKED"
            block_reasons.append(f"approved_packet_status_{export_value.lower()}")
        else:
            approved_packet_status = "INVALID"
            warnings.append("approved_packet_json_missing_export_status")
            block_reasons.append("approved_packet_invalid")

    audit_payload, audit_state = _read_json_object(audit_index_json)
    if audit_state == "MISSING":
        audit_status = "MISSING"
        block_reasons.append("audit_index_missing")
    elif audit_state == "INVALID":
        audit_status = "INVALID"
        warnings.append(f"audit_index_json_invalid path={audit_index_json}")
        block_reasons.append("audit_index_invalid")
    else:
        audit_value = audit_payload.get("audit_status") if audit_payload else None
        if isinstance(audit_value, str) and audit_value == "READY":
            audit_status = "READY"
        elif isinstance(audit_value, str):
            audit_status = "BLOCKED"
            block_reasons.append(f"audit_status_{audit_value.lower()}")
        else:
            audit_status = "INVALID"
            warnings.append("audit_index_json_missing_audit_status")
            block_reasons.append("audit_index_invalid")

    manifest_id: str | None = None
    manifest_rows = 0
    planned_row_count = 0
    batch_count = 0
    command_status_counts: list[tuple[str, int]] = []
    planned_rows: list[WalletFlowGuardedHandoffRow] = []

    if plan_payload is not None:
        mid = plan_payload.get("manifest_id")
        if isinstance(mid, str):
            manifest_id = mid

        rows_value = plan_payload.get("manifest_rows")
        if isinstance(rows_value, int):
            manifest_rows = rows_value

        batch_value = plan_payload.get("batch_count")
        if isinstance(batch_value, int):
            batch_count = batch_value

        cs_counts_value = plan_payload.get("command_status_counts")
        command_status_counts = _parse_command_status_counts(cs_counts_value)

        planned_rows_value = plan_payload.get("planned_rows")
        if isinstance(planned_rows_value, list):
            planned_row_count = len(planned_rows_value)
            planned_rows = _parse_planned_rows(planned_rows_value, limit=10)
        else:
            warnings.append("dry_run_plan_json_missing_planned_rows")

    if plan_status != "READY":
        block_reasons.append(f"plan_status_not_ready:{plan_status}")
    if approved_packet_status != "PASS":
        block_reasons.append(f"approved_packet_status_not_pass:{approved_packet_status}")
    if audit_status != "READY":
        block_reasons.append(f"audit_status_not_ready:{audit_status}")

    normalized_block_reasons = sorted(set(block_reasons))
    handoff_status = (
        "READY_FOR_MANUAL_APPROVAL" if not normalized_block_reasons else "BLOCKED"
    )

    return WalletFlowGuardedOperatorHandoff(
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
        execution_mode="manual_review_only",
        planned_rows=planned_rows,
    )


def render_wallet_flow_guarded_operator_handoff(handoff: WalletFlowGuardedOperatorHandoff) -> str:
    lines = [
        "# Wallet Flow Guarded Operator Handoff",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Guarded operator handoff only.",
        "Manual approval required.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "Approved for human review only.",
        "",
        "## Handoff Status",
        "",
        f"- handoff_status: {handoff.handoff_status}",
        f"- plan_status: {handoff.plan_status}",
        f"- approved_packet_status: {handoff.approved_packet_status}",
        f"- audit_status: {handoff.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {handoff.manifest_id or '(missing)'}",
        f"- manifest_rows: {handoff.manifest_rows}",
        f"- planned_row_count: {handoff.planned_row_count}",
        f"- batch_count: {handoff.batch_count}",
        f"- approval_required: {handoff.approval_required}",
        f"- manual_operator_only: {handoff.manual_operator_only}",
        f"- no_execution: {handoff.no_execution}",
        f"- execution_mode: {handoff.execution_mode}",
        "",
        "## Command Status Counts",
        "",
    ]

    if handoff.command_status_counts:
        for status, count in handoff.command_status_counts:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Planned Rows (First 10)", ""])
    if not handoff.planned_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | idempotency_key | row_checksum | command |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|")
        for row in handoff.planned_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.idempotency_key} | {row.row_checksum} | {row.command} |"
            )

    lines.extend(
        [
            "",
            "## Approval Checklist",
            "",
            "- Confirm source market coverage is acceptable.",
            "- Confirm command template is review-only.",
            "- Confirm manifest review gate is PASS.",
            "- Confirm approved packet export_status is PASS.",
            "- Confirm audit_status is READY.",
            "- Confirm no live execution adapter is enabled.",
            "- Confirm no ingestion has been executed.",
        ]
    )

    lines.extend(["", "## Block Reasons", ""])
    if handoff.block_reasons:
        for reason in handoff.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if handoff.warnings:
        for warning in handoff.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


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


def _parse_planned_rows(value: list[object], *, limit: int) -> list[WalletFlowGuardedHandoffRow]:
    rows: list[WalletFlowGuardedHandoffRow] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowGuardedHandoffRow(
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


def _handoff_json_payload(handoff: WalletFlowGuardedOperatorHandoff) -> dict[str, object]:
    return {
        "handoff_status": handoff.handoff_status,
        "plan_status": handoff.plan_status,
        "approved_packet_status": handoff.approved_packet_status,
        "audit_status": handoff.audit_status,
        "block_reasons": handoff.block_reasons,
        "warnings": handoff.warnings,
        "manifest_id": handoff.manifest_id,
        "manifest_rows": handoff.manifest_rows,
        "planned_row_count": handoff.planned_row_count,
        "batch_count": handoff.batch_count,
        "command_status_counts": [
            {"command_status": status, "count": count}
            for status, count in handoff.command_status_counts
        ],
        "approval_required": handoff.approval_required,
        "manual_operator_only": handoff.manual_operator_only,
        "no_execution": handoff.no_execution,
        "execution_mode": handoff.execution_mode,
        "planned_rows": [asdict(row) for row in handoff.planned_rows],
        "approval_checklist": [
            "Confirm source market coverage is acceptable.",
            "Confirm command template is review-only.",
            "Confirm manifest review gate is PASS.",
            "Confirm approved packet export_status is PASS.",
            "Confirm audit_status is READY.",
            "Confirm no live execution adapter is enabled.",
            "Confirm no ingestion has been executed.",
        ],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "guarded_operator_handoff_only": True,
            "manual_approval_required": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "approved_for_human_review_only": True,
        },
    }


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
