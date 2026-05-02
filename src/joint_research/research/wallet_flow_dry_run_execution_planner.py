"""Wallet-flow dry-run execution planner (preview only).

This module never executes manifest commands, never shells out, and never
performs ingestion. It only builds a deterministic preview plan.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DRY_RUN_PLAN_MD_FILENAME = "wallet_flow_dry_run_execution_plan.md"
DRY_RUN_PLAN_JSON_FILENAME = "wallet_flow_dry_run_execution_plan.json"


@dataclass(frozen=True)
class WalletFlowDryRunPlannedRow:
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
class WalletFlowDryRunExecutionPlan:
    plan_status: str
    block_reasons: list[str]
    warnings: list[str]
    manifest_id: str | None
    manifest_rows: int
    batch_count: int
    command_status_counts: list[tuple[str, int]]
    approved_packet_status: str
    audit_status: str
    dry_run: bool
    execution_mode: str
    no_execution: bool
    planned_rows: list[WalletFlowDryRunPlannedRow]


@dataclass(frozen=True)
class WalletFlowDryRunExecutionPlanArtifacts:
    plan_md: Path
    plan_json: Path
    plan: WalletFlowDryRunExecutionPlan


def write_wallet_flow_dry_run_execution_plan(
    *,
    manifest_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
    output_dir: Path,
) -> WalletFlowDryRunExecutionPlanArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    plan_md = output_dir / DRY_RUN_PLAN_MD_FILENAME
    plan_json = output_dir / DRY_RUN_PLAN_JSON_FILENAME
    plan_md.write_text(render_wallet_flow_dry_run_execution_plan(plan))
    plan_json.write_text(_stable_json(_plan_json_payload(plan)) + "\n")

    return WalletFlowDryRunExecutionPlanArtifacts(
        plan_md=plan_md,
        plan_json=plan_json,
        plan=plan,
    )


def build_wallet_flow_dry_run_execution_plan(
    *,
    manifest_json: Path,
    approved_packet_json: Path,
    audit_index_json: Path,
) -> WalletFlowDryRunExecutionPlan:
    warnings: list[str] = []
    block_reasons: list[str] = []

    manifest_payload, manifest_state = _read_json_object(manifest_json)
    if manifest_state != "OK":
        warnings.append(f"manifest_json_{manifest_state.lower()} path={manifest_json}")
        block_reasons.append(f"manifest_json_{manifest_state.lower()}")

    rows: list[object] = []
    manifest_id: str | None = None
    manifest_rows = 0
    batch_count = 0
    command_status_counts: list[tuple[str, int]] = []
    planned_rows: list[WalletFlowDryRunPlannedRow] = []

    if manifest_payload is not None:
        rows_value = manifest_payload.get("rows")
        if isinstance(rows_value, list):
            rows = rows_value
        else:
            warnings.append("manifest_json_rows_not_list")
            block_reasons.append("manifest_json_rows_not_list")

        id_value = manifest_payload.get("manifest_id")
        if isinstance(id_value, str):
            manifest_id = id_value

        declared_rows = manifest_payload.get("manifest_rows")
        if isinstance(declared_rows, int):
            manifest_rows = declared_rows
        else:
            manifest_rows = len(rows)

        batch_count = len(
            {
                int(row["batch_id"])
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("batch_id"), int)
            }
        )
        command_status_counts = _command_status_counts(rows)
        planned_rows = _planned_rows(rows, limit=10)

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

    if approved_packet_status != "PASS":
        block_reasons.append(f"approved_packet_status_not_pass:{approved_packet_status}")
    if audit_status != "READY":
        block_reasons.append(f"audit_status_not_ready:{audit_status}")

    normalized_block_reasons = sorted(set(block_reasons))
    plan_status = "READY" if not normalized_block_reasons else "BLOCKED"

    return WalletFlowDryRunExecutionPlan(
        plan_status=plan_status,
        block_reasons=normalized_block_reasons,
        warnings=warnings,
        manifest_id=manifest_id,
        manifest_rows=manifest_rows,
        batch_count=batch_count,
        command_status_counts=command_status_counts,
        approved_packet_status=approved_packet_status,
        audit_status=audit_status,
        dry_run=True,
        execution_mode="preview_only",
        no_execution=True,
        planned_rows=planned_rows,
    )


def render_wallet_flow_dry_run_execution_plan(plan: WalletFlowDryRunExecutionPlan) -> str:
    lines = [
        "# Wallet Flow Dry-Run Execution Plan",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Dry-run execution plan only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "Approved for human review only.",
        "",
        "## Plan Status",
        "",
        f"- plan_status: {plan.plan_status}",
        f"- approved_packet_status: {plan.approved_packet_status}",
        f"- audit_status: {plan.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {plan.manifest_id or '(missing)'}",
        f"- manifest_rows: {plan.manifest_rows}",
        f"- batch_count: {plan.batch_count}",
        f"- dry_run: {plan.dry_run}",
        f"- execution_mode: {plan.execution_mode}",
        f"- no_execution: {plan.no_execution}",
        "",
        "## Command Status Counts",
        "",
    ]

    if plan.command_status_counts:
        for status, count in plan.command_status_counts:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Planned Rows (First 10)", ""])
    if not plan.planned_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | idempotency_key | row_checksum | command |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|")
        for row in plan.planned_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.idempotency_key} | {row.row_checksum} | {row.command} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if plan.block_reasons:
        for reason in plan.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if plan.warnings:
        for warning in plan.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _command_status_counts(rows: list[object]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = row.get("command_status")
        if not isinstance(status, str) or not status:
            status = "(missing)"
        counts[status] = counts.get(status, 0) + 1
    return sorted(counts.items(), key=lambda item: item[0])


def _planned_rows(rows: list[object], *, limit: int) -> list[WalletFlowDryRunPlannedRow]:
    planned: list[WalletFlowDryRunPlannedRow] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if len(planned) >= limit:
            break
        planned.append(
            WalletFlowDryRunPlannedRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("ingest_command")),
            )
        )
    return planned


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


def _plan_json_payload(plan: WalletFlowDryRunExecutionPlan) -> dict[str, object]:
    return {
        "plan_status": plan.plan_status,
        "block_reasons": plan.block_reasons,
        "warnings": plan.warnings,
        "manifest_id": plan.manifest_id,
        "manifest_rows": plan.manifest_rows,
        "batch_count": plan.batch_count,
        "command_status_counts": [
            {"command_status": status, "count": count}
            for status, count in plan.command_status_counts
        ],
        "approved_packet_status": plan.approved_packet_status,
        "audit_status": plan.audit_status,
        "dry_run": plan.dry_run,
        "execution_mode": plan.execution_mode,
        "no_execution": plan.no_execution,
        "planned_rows": [asdict(row) for row in plan.planned_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "dry_run_execution_plan_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
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
