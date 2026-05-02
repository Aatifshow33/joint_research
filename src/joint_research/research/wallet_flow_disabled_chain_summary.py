"""Wallet-flow end-to-end disabled chain summary (non-executing).

This module summarizes the approval/execution chain state and proves it
remains disabled by policy. It never executes commands, shells out, performs
ingestion, uses network, mutates databases, or places orders.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

DISABLED_CHAIN_SUMMARY_MD_FILENAME = "wallet_flow_disabled_chain_summary.md"
DISABLED_CHAIN_SUMMARY_JSON_FILENAME = "wallet_flow_disabled_chain_summary.json"
DISABLED_REASON = "DISABLED_BY_POLICY"
FINAL_CONFIRMATION = (
    "Wallet-flow chain is disabled by policy; no execution was attempted."
)


@dataclass(frozen=True)
class WalletFlowDisabledChainSourceArtifact:
    name: str
    path: str
    state: str
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True)
class WalletFlowDisabledChainCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class WalletFlowDisabledChainRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    contract_row_status: str
    receipt_row_status: str
    adapter_row_status: str
    run_row_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    chain_row_status: str


@dataclass(frozen=True)
class WalletFlowDisabledChainSummary:
    chain_status: str
    contract_status: str
    receipt_status: str
    adapter_status: str
    run_status: str
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
    chain_summary_version: str
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
    final_confirmation: str
    source_artifacts: list[WalletFlowDisabledChainSourceArtifact]
    chain_checks: list[WalletFlowDisabledChainCheck]
    block_reasons: list[str]
    warnings: list[str]
    chain_rows: list[WalletFlowDisabledChainRow]


@dataclass(frozen=True)
class WalletFlowDisabledChainSummaryArtifacts:
    summary_md: Path
    summary_json: Path
    summary: WalletFlowDisabledChainSummary


def write_wallet_flow_disabled_chain_summary(
    *,
    approval_execution_contract_json: Path,
    contract_audit_receipt_json: Path,
    disabled_adapter_interface_json: Path,
    disabled_adapter_run_receipt_json: Path,
    output_dir: Path,
) -> WalletFlowDisabledChainSummaryArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=approval_execution_contract_json,
        contract_audit_receipt_json=contract_audit_receipt_json,
        disabled_adapter_interface_json=disabled_adapter_interface_json,
        disabled_adapter_run_receipt_json=disabled_adapter_run_receipt_json,
    )

    summary_md = output_dir / DISABLED_CHAIN_SUMMARY_MD_FILENAME
    summary_json = output_dir / DISABLED_CHAIN_SUMMARY_JSON_FILENAME
    summary_md.write_text(render_wallet_flow_disabled_chain_summary(summary))
    summary_json.write_text(_stable_json(_summary_json_payload(summary)) + "\n")

    return WalletFlowDisabledChainSummaryArtifacts(
        summary_md=summary_md,
        summary_json=summary_json,
        summary=summary,
    )


def build_wallet_flow_disabled_chain_summary(
    *,
    approval_execution_contract_json: Path,
    contract_audit_receipt_json: Path,
    disabled_adapter_interface_json: Path,
    disabled_adapter_run_receipt_json: Path,
) -> WalletFlowDisabledChainSummary:
    warnings: list[str] = []
    block_reasons: list[str] = []

    contract_art = _load_json_artifact(
        name="approval_execution_contract_json",
        path=approval_execution_contract_json,
        warnings=warnings,
    )
    receipt_art = _load_json_artifact(
        name="contract_audit_receipt_json",
        path=contract_audit_receipt_json,
        warnings=warnings,
    )
    adapter_art = _load_json_artifact(
        name="disabled_adapter_interface_json",
        path=disabled_adapter_interface_json,
        warnings=warnings,
    )
    run_art = _load_json_artifact(
        name="disabled_adapter_run_receipt_json",
        path=disabled_adapter_run_receipt_json,
        warnings=warnings,
    )

    artifacts = [contract_art, receipt_art, adapter_art, run_art]
    source_artifacts = [
        WalletFlowDisabledChainSourceArtifact(
            name=art["name"],
            path=art["path"],
            state=art["state"],
            size_bytes=art["size_bytes"],
            sha256=art["sha256"],
        )
        for art in artifacts
    ]

    for artifact in artifacts:
        if artifact["state"] == "MISSING":
            block_reasons.append(f"{artifact['name']}_missing")
        elif artifact["state"] == "INVALID":
            block_reasons.append(f"{artifact['name']}_invalid")

    contract_payload = contract_art["payload"]
    receipt_payload = receipt_art["payload"]
    adapter_payload = adapter_art["payload"]
    run_payload = run_art["payload"]

    contract_status = _status_from_payload(contract_payload, "contract_status", contract_art["state"])
    receipt_status = _status_from_payload(receipt_payload, "receipt_status", receipt_art["state"])
    adapter_status = _status_from_payload(adapter_payload, "adapter_status", adapter_art["state"])
    run_status = _status_from_payload(run_payload, "run_status", run_art["state"])

    ledger_status = _coalesce_status(
        _payload_str(run_payload, "ledger_status", default="unknown"),
        _payload_str(adapter_payload, "ledger_status", default="unknown"),
        _payload_str(receipt_payload, "ledger_status", default="unknown"),
        _payload_str(contract_payload, "ledger_status", default="unknown"),
    )
    decision = _normalize_decision(
        _coalesce_status(
            _payload_str(run_payload, "decision", default="unknown"),
            _payload_str(adapter_payload, "decision", default="unknown"),
            _payload_str(receipt_payload, "decision", default="unknown"),
            _payload_str(contract_payload, "decision", default="unknown"),
        )
    )
    reviewer = _coalesce_str(
        _payload_str(run_payload, "reviewer", default=""),
        _payload_str(adapter_payload, "reviewer", default=""),
        _payload_str(receipt_payload, "reviewer", default=""),
        _payload_str(contract_payload, "reviewer", default=""),
    )
    review_note = _coalesce_str(
        _payload_str(run_payload, "review_note", default=""),
        _payload_str(adapter_payload, "review_note", default=""),
        _payload_str(receipt_payload, "review_note", default=""),
        _payload_str(contract_payload, "review_note", default=""),
    )
    handoff_status = _coalesce_status(
        _payload_str(run_payload, "handoff_status", default="unknown"),
        _payload_str(adapter_payload, "handoff_status", default="unknown"),
        _payload_str(receipt_payload, "handoff_status", default="unknown"),
        _payload_str(contract_payload, "handoff_status", default="unknown"),
    )
    plan_status = _coalesce_status(
        _payload_str(run_payload, "plan_status", default="unknown"),
        _payload_str(adapter_payload, "plan_status", default="unknown"),
        _payload_str(receipt_payload, "plan_status", default="unknown"),
        _payload_str(contract_payload, "plan_status", default="unknown"),
    )
    approved_packet_status = _coalesce_status(
        _payload_str(run_payload, "approved_packet_status", default="unknown"),
        _payload_str(adapter_payload, "approved_packet_status", default="unknown"),
        _payload_str(receipt_payload, "approved_packet_status", default="unknown"),
        _payload_str(contract_payload, "approved_packet_status", default="unknown"),
    )
    audit_status = _coalesce_status(
        _payload_str(run_payload, "audit_status", default="unknown"),
        _payload_str(adapter_payload, "audit_status", default="unknown"),
        _payload_str(receipt_payload, "audit_status", default="unknown"),
        _payload_str(contract_payload, "audit_status", default="unknown"),
    )

    manifest_id_values = _collect_optional_strs(
        _payload_optional_str(contract_payload, "manifest_id"),
        _payload_optional_str(receipt_payload, "manifest_id"),
        _payload_optional_str(adapter_payload, "manifest_id"),
        _payload_optional_str(run_payload, "manifest_id"),
    )
    manifest_rows_values = _collect_positive_ints(
        _payload_int(contract_payload, "manifest_rows"),
        _payload_int(receipt_payload, "manifest_rows"),
        _payload_int(adapter_payload, "manifest_rows"),
        _payload_int(run_payload, "manifest_rows"),
    )
    planned_row_count_values = _collect_positive_ints(
        _payload_int(contract_payload, "planned_row_count"),
        _payload_int(receipt_payload, "planned_row_count"),
        _payload_int(adapter_payload, "planned_row_count"),
        _payload_int(run_payload, "planned_row_count"),
    )

    manifest_id = manifest_id_values[0] if manifest_id_values else None
    manifest_rows = manifest_rows_values[0] if manifest_rows_values else 0
    planned_row_count = planned_row_count_values[0] if planned_row_count_values else 0

    bool_adapter_enabled = _coalesce_bool(
        _payload_bool(run_payload, "adapter_enabled"),
        _payload_bool(adapter_payload, "adapter_enabled"),
    )
    bool_execution_enabled = _coalesce_bool(
        _payload_bool(run_payload, "execution_enabled"),
        _payload_bool(adapter_payload, "execution_enabled"),
    )
    bool_network_enabled = _coalesce_bool(
        _payload_bool(run_payload, "network_enabled"),
        _payload_bool(adapter_payload, "network_enabled"),
    )
    bool_ingestion_enabled = _coalesce_bool(
        _payload_bool(run_payload, "ingestion_enabled"),
        _payload_bool(adapter_payload, "ingestion_enabled"),
    )
    bool_shell_enabled = _coalesce_bool(
        _payload_bool(run_payload, "shell_enabled"),
        _payload_bool(adapter_payload, "shell_enabled"),
    )
    bool_order_enabled = _coalesce_bool(
        _payload_bool(run_payload, "order_placement_enabled"),
        _payload_bool(adapter_payload, "order_placement_enabled"),
    )
    bool_db_mutation_enabled = _coalesce_bool(
        _payload_bool(run_payload, "database_mutation_enabled"),
        _payload_bool(adapter_payload, "database_mutation_enabled"),
    )
    bool_approval_required = _coalesce_bool(
        _payload_bool(run_payload, "approval_required"),
        _payload_bool(adapter_payload, "approval_required"),
        _payload_bool(receipt_payload, "approval_required"),
        _payload_bool(contract_payload, "approval_required"),
    )
    bool_manual_operator_only = _coalesce_bool(
        _payload_bool(run_payload, "manual_operator_only"),
        _payload_bool(adapter_payload, "manual_operator_only"),
        _payload_bool(receipt_payload, "manual_operator_only"),
        _payload_bool(contract_payload, "manual_operator_only"),
    )
    bool_no_execution = _coalesce_bool(
        _payload_bool(run_payload, "no_execution"),
        _payload_bool(adapter_payload, "no_execution"),
        _payload_bool(receipt_payload, "no_execution"),
        _payload_bool(contract_payload, "no_execution"),
    )
    bool_no_ingestion = _coalesce_bool(
        _payload_bool(run_payload, "no_ingestion"),
        _payload_bool(adapter_payload, "no_ingestion"),
        _payload_bool(receipt_payload, "no_ingestion"),
        _payload_bool(contract_payload, "no_ingestion"),
    )
    bool_no_orders = _coalesce_bool(
        _payload_bool(run_payload, "no_orders"),
        _payload_bool(adapter_payload, "no_orders"),
        _payload_bool(receipt_payload, "no_orders"),
    )

    chain_checks = _build_chain_checks(
        contract_status=contract_status,
        receipt_status=receipt_status,
        adapter_status=adapter_status,
        run_status=run_status,
        adapter_enabled=bool_adapter_enabled,
        execution_enabled=bool_execution_enabled,
        network_enabled=bool_network_enabled,
        ingestion_enabled=bool_ingestion_enabled,
        shell_enabled=bool_shell_enabled,
        order_placement_enabled=bool_order_enabled,
        database_mutation_enabled=bool_db_mutation_enabled,
        approval_required=bool_approval_required,
        manual_operator_only=bool_manual_operator_only,
        no_execution=bool_no_execution,
        no_ingestion=bool_no_ingestion,
        no_orders=bool_no_orders,
        manifest_id_values=manifest_id_values,
        manifest_rows_values=manifest_rows_values,
        planned_row_count_values=planned_row_count_values,
    )

    for check in chain_checks:
        if check.status == "FAIL" and check.name in {
            "manifest_id_consistent",
            "manifest_rows_consistent",
            "planned_row_count_consistent",
        }:
            block_reasons.append(f"chain_check_failed:{check.name}")

    missing_or_invalid = any(
        art["state"] in {"MISSING", "INVALID"} for art in artifacts
    )
    any_awaiting = any(
        value == "AWAITING_APPROVAL"
        for value in (contract_status, receipt_status, adapter_status, run_status)
    )
    any_rejected = any(
        value == "REJECTED"
        for value in (contract_status, receipt_status, adapter_status, run_status)
    )

    required_pass_for_confirmed = {
        "contract_ready",
        "receipt_ready",
        "adapter_disabled_by_policy",
        "run_disabled_confirmed",
        "adapter_enabled_false",
        "execution_enabled_false",
        "network_enabled_false",
        "ingestion_enabled_false",
        "shell_enabled_false",
        "order_placement_enabled_false",
        "database_mutation_enabled_false",
        "approval_required_true",
        "manual_operator_only_true",
        "no_execution_true",
        "no_ingestion_true",
        "no_orders_true",
        "manifest_id_consistent",
        "manifest_rows_consistent",
        "planned_row_count_consistent",
    }
    pass_map = {check.name: check.status == "PASS" for check in chain_checks}
    confirmed_ready = all(pass_map.get(name, False) for name in required_pass_for_confirmed)

    normalized_block_reasons = sorted(set(block_reasons))
    if missing_or_invalid:
        chain_status = "BLOCKED"
    elif confirmed_ready:
        chain_status = "DISABLED_CHAIN_CONFIRMED"
    elif any_rejected:
        chain_status = "REJECTED"
    elif any_awaiting:
        chain_status = "AWAITING_APPROVAL"
    else:
        chain_status = "BLOCKED"
        if not normalized_block_reasons:
            normalized_block_reasons = ["disabled_chain_conditions_not_met"]

    chain_rows = _build_chain_rows(
        run_payload=run_payload,
        adapter_payload=adapter_payload,
        receipt_payload=receipt_payload,
        contract_payload=contract_payload,
        chain_status=chain_status,
        limit=10,
    )

    return WalletFlowDisabledChainSummary(
        chain_status=chain_status,
        contract_status=contract_status,
        receipt_status=receipt_status,
        adapter_status=adapter_status,
        run_status=run_status,
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
        chain_summary_version="wallet_flow_disabled_chain_summary_v1",
        execution_mode="disabled_chain_summary_only",
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
        final_confirmation=FINAL_CONFIRMATION,
        source_artifacts=source_artifacts,
        chain_checks=chain_checks,
        block_reasons=normalized_block_reasons,
        warnings=warnings,
        chain_rows=chain_rows,
    )


def render_wallet_flow_disabled_chain_summary(summary: WalletFlowDisabledChainSummary) -> str:
    lines = [
        "# Wallet Flow Disabled Chain Summary",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Disabled chain summary only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Chain is disabled by policy.",
        "Summary records disabled chain state only.",
        "",
        "## Chain Status",
        "",
        f"- chain_status: {summary.chain_status}",
        f"- contract_status: {summary.contract_status}",
        f"- receipt_status: {summary.receipt_status}",
        f"- adapter_status: {summary.adapter_status}",
        f"- run_status: {summary.run_status}",
        f"- ledger_status: {summary.ledger_status}",
        f"- decision: {summary.decision}",
        f"- reviewer: {summary.reviewer or '(none)'}",
        f"- review_note: {summary.review_note or '(none)'}",
        f"- handoff_status: {summary.handoff_status}",
        f"- plan_status: {summary.plan_status}",
        f"- approved_packet_status: {summary.approved_packet_status}",
        f"- audit_status: {summary.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {summary.manifest_id or '(missing)'}",
        f"- manifest_rows: {summary.manifest_rows}",
        f"- planned_row_count: {summary.planned_row_count}",
        f"- chain_summary_version: {summary.chain_summary_version}",
        f"- execution_mode: {summary.execution_mode}",
        f"- adapter_enabled: {summary.adapter_enabled}",
        f"- execution_enabled: {summary.execution_enabled}",
        f"- network_enabled: {summary.network_enabled}",
        f"- ingestion_enabled: {summary.ingestion_enabled}",
        f"- shell_enabled: {summary.shell_enabled}",
        f"- order_placement_enabled: {summary.order_placement_enabled}",
        f"- database_mutation_enabled: {summary.database_mutation_enabled}",
        f"- approval_required: {summary.approval_required}",
        f"- manual_operator_only: {summary.manual_operator_only}",
        f"- no_execution: {summary.no_execution}",
        f"- no_ingestion: {summary.no_ingestion}",
        f"- no_orders: {summary.no_orders}",
        f"- disabled_reason: {summary.disabled_reason}",
        f"- final_confirmation: {summary.final_confirmation}",
        "",
        "## Source Artifacts",
        "",
        "| name | path | state | size_bytes | sha256 |",
        "|---|---|---|---:|---|",
    ]
    for source in summary.source_artifacts:
        lines.append(
            f"| {source.name} | {source.path} | {source.state} | "
            f"{source.size_bytes if source.size_bytes is not None else ''} | {source.sha256 or ''} |"
        )

    lines.extend(["", "## Chain Checks", ""])
    lines.append("| name | status | detail |")
    lines.append("|---|---|---|")
    for check in summary.chain_checks:
        lines.append(f"| {check.name} | {check.status} | {check.detail} |")

    lines.extend(["", "## Chain Rows (First 10)", ""])
    if not summary.chain_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | contract_row_status | receipt_row_status | adapter_row_status | run_row_status | idempotency_key | row_checksum | command | chain_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|")
        for row in summary.chain_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.contract_row_status} | {row.receipt_row_status} | "
                f"{row.adapter_row_status} | {row.run_row_status} | {row.idempotency_key} | "
                f"{row.row_checksum} | {row.command} | {row.chain_row_status} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if summary.block_reasons:
        for reason in summary.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if summary.warnings:
        for warning in summary.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _build_chain_checks(
    *,
    contract_status: str,
    receipt_status: str,
    adapter_status: str,
    run_status: str,
    adapter_enabled: bool | None,
    execution_enabled: bool | None,
    network_enabled: bool | None,
    ingestion_enabled: bool | None,
    shell_enabled: bool | None,
    order_placement_enabled: bool | None,
    database_mutation_enabled: bool | None,
    approval_required: bool | None,
    manual_operator_only: bool | None,
    no_execution: bool | None,
    no_ingestion: bool | None,
    no_orders: bool | None,
    manifest_id_values: list[str],
    manifest_rows_values: list[int],
    planned_row_count_values: list[int],
) -> list[WalletFlowDisabledChainCheck]:
    checks: list[WalletFlowDisabledChainCheck] = []
    checks.append(_expected_str_check("contract_ready", contract_status, "CONTRACT_READY"))
    checks.append(_expected_str_check("receipt_ready", receipt_status, "RECEIPT_READY"))
    checks.append(_expected_str_check("adapter_disabled_by_policy", adapter_status, "DISABLED_BY_POLICY"))
    checks.append(_expected_str_check("run_disabled_confirmed", run_status, "DISABLED_BY_POLICY_CONFIRMED"))
    checks.append(_expected_bool_false_check("adapter_enabled_false", adapter_enabled))
    checks.append(_expected_bool_false_check("execution_enabled_false", execution_enabled))
    checks.append(_expected_bool_false_check("network_enabled_false", network_enabled))
    checks.append(_expected_bool_false_check("ingestion_enabled_false", ingestion_enabled))
    checks.append(_expected_bool_false_check("shell_enabled_false", shell_enabled))
    checks.append(_expected_bool_false_check("order_placement_enabled_false", order_placement_enabled))
    checks.append(_expected_bool_false_check("database_mutation_enabled_false", database_mutation_enabled))
    checks.append(_expected_bool_true_check("approval_required_true", approval_required))
    checks.append(_expected_bool_true_check("manual_operator_only_true", manual_operator_only))
    checks.append(_expected_bool_true_check("no_execution_true", no_execution))
    checks.append(_expected_bool_true_check("no_ingestion_true", no_ingestion))
    checks.append(_expected_bool_true_check("no_orders_true", no_orders))
    checks.append(_consistency_check("manifest_id_consistent", [str(v) for v in manifest_id_values]))
    checks.append(_consistency_check("manifest_rows_consistent", [str(v) for v in manifest_rows_values]))
    checks.append(_consistency_check("planned_row_count_consistent", [str(v) for v in planned_row_count_values]))
    return checks


def _build_chain_rows(
    *,
    run_payload: dict[str, object] | None,
    adapter_payload: dict[str, object] | None,
    receipt_payload: dict[str, object] | None,
    contract_payload: dict[str, object] | None,
    chain_status: str,
    limit: int,
) -> list[WalletFlowDisabledChainRow]:
    rows_value = _first_list(
        run_payload.get("run_rows") if run_payload else None,
        adapter_payload.get("adapter_preview_rows") if adapter_payload else None,
        receipt_payload.get("receipt_rows") if receipt_payload else None,
        contract_payload.get("planned_rows") if contract_payload else None,
    )
    if rows_value is None:
        return []

    if chain_status == "DISABLED_CHAIN_CONFIRMED":
        row_status = "DISABLED_CHAIN_CONFIRMED"
    elif chain_status == "AWAITING_APPROVAL":
        row_status = "AWAITING_APPROVAL"
    elif chain_status == "REJECTED":
        row_status = "REJECTED"
    else:
        row_status = "BLOCKED"

    rows: list[WalletFlowDisabledChainRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowDisabledChainRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                contract_row_status=_to_str(row.get("contract_row_status")),
                receipt_row_status=_to_str(row.get("receipt_row_status")),
                adapter_row_status=_to_str(row.get("adapter_row_status")),
                run_row_status=_to_str(row.get("run_row_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                chain_row_status=row_status,
            )
        )
    return rows


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


def _summary_json_payload(summary: WalletFlowDisabledChainSummary) -> dict[str, object]:
    return {
        "chain_status": summary.chain_status,
        "contract_status": summary.contract_status,
        "receipt_status": summary.receipt_status,
        "adapter_status": summary.adapter_status,
        "run_status": summary.run_status,
        "ledger_status": summary.ledger_status,
        "decision": summary.decision,
        "reviewer": summary.reviewer,
        "review_note": summary.review_note,
        "handoff_status": summary.handoff_status,
        "plan_status": summary.plan_status,
        "approved_packet_status": summary.approved_packet_status,
        "audit_status": summary.audit_status,
        "manifest_id": summary.manifest_id,
        "manifest_rows": summary.manifest_rows,
        "planned_row_count": summary.planned_row_count,
        "chain_summary_version": summary.chain_summary_version,
        "execution_mode": summary.execution_mode,
        "adapter_enabled": summary.adapter_enabled,
        "execution_enabled": summary.execution_enabled,
        "network_enabled": summary.network_enabled,
        "ingestion_enabled": summary.ingestion_enabled,
        "shell_enabled": summary.shell_enabled,
        "order_placement_enabled": summary.order_placement_enabled,
        "database_mutation_enabled": summary.database_mutation_enabled,
        "approval_required": summary.approval_required,
        "manual_operator_only": summary.manual_operator_only,
        "no_execution": summary.no_execution,
        "no_ingestion": summary.no_ingestion,
        "no_orders": summary.no_orders,
        "disabled_reason": summary.disabled_reason,
        "final_confirmation": summary.final_confirmation,
        "source_artifacts": [asdict(source) for source in summary.source_artifacts],
        "chain_checks": [asdict(check) for check in summary.chain_checks],
        "block_reasons": summary.block_reasons,
        "warnings": summary.warnings,
        "chain_rows": [asdict(row) for row in summary.chain_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "disabled_chain_summary_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "chain_disabled_by_policy": True,
            "summary_records_disabled_chain_state_only": True,
        },
    }


def _status_from_payload(
    payload: dict[str, object] | None, key: str, state: str
) -> str:
    if state in {"MISSING", "INVALID"}:
        return state
    return _payload_str(payload, key, default="unknown")


def _expected_str_check(name: str, value: str, expected: str) -> WalletFlowDisabledChainCheck:
    if value == expected:
        return WalletFlowDisabledChainCheck(name=name, status="PASS", detail=f"value={value}")
    return WalletFlowDisabledChainCheck(
        name=name, status="FAIL", detail=f"value={value} expected={expected}"
    )


def _expected_bool_false_check(name: str, value: bool | None) -> WalletFlowDisabledChainCheck:
    if value is None:
        return WalletFlowDisabledChainCheck(name=name, status="SKIP", detail="value_missing")
    if value is False:
        return WalletFlowDisabledChainCheck(name=name, status="PASS", detail="value=false")
    return WalletFlowDisabledChainCheck(name=name, status="FAIL", detail="value=true expected=false")


def _expected_bool_true_check(name: str, value: bool | None) -> WalletFlowDisabledChainCheck:
    if value is None:
        return WalletFlowDisabledChainCheck(name=name, status="SKIP", detail="value_missing")
    if value is True:
        return WalletFlowDisabledChainCheck(name=name, status="PASS", detail="value=true")
    return WalletFlowDisabledChainCheck(name=name, status="FAIL", detail="value=false expected=true")


def _consistency_check(name: str, values: list[str]) -> WalletFlowDisabledChainCheck:
    unique_values = sorted(set(values))
    if len(unique_values) <= 1:
        if not unique_values:
            return WalletFlowDisabledChainCheck(name=name, status="SKIP", detail="insufficient_values")
        return WalletFlowDisabledChainCheck(name=name, status="PASS", detail=f"value={unique_values[0]}")
    return WalletFlowDisabledChainCheck(
        name=name,
        status="FAIL",
        detail=f"values={','.join(unique_values)}",
    )


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


def _payload_bool(payload: dict[str, object] | None, key: str) -> bool | None:
    if payload is None:
        return None
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return None


def _normalize_decision(value: str) -> str:
    lowered = value.lower()
    if lowered in {"pending", "approve", "reject"}:
        return lowered
    return "unknown"


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


def _coalesce_bool(*values: bool | None) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def _first_list(*values: object) -> list[object] | None:
    for value in values:
        if isinstance(value, list):
            return value
    return None


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
