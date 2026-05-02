"""Wallet-flow disabled policy regression guard (non-executing).

This module validates that the wallet-flow disabled chain summary still
enforces the non-execution policy boundary. It never executes commands, never
shells out, never calls network, never performs ingestion, and never places
orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DISABLED_POLICY_GUARD_MD_FILENAME = "wallet_flow_disabled_policy_guard.md"
DISABLED_POLICY_GUARD_JSON_FILENAME = "wallet_flow_disabled_policy_guard.json"
DISABLED_REASON = "DISABLED_BY_POLICY"
GUARD_CONFIRMATION = (
    "Wallet-flow disabled policy guard passed; execution remains impossible by policy."
)


@dataclass(frozen=True)
class WalletFlowDisabledPolicyCheck:
    name: str
    status: str
    expected: str
    actual: str
    detail: str


@dataclass(frozen=True)
class WalletFlowDisabledPolicyGuardRow:
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
    chain_row_status: str
    idempotency_key: str
    row_checksum: str
    command: str
    guard_row_status: str


@dataclass(frozen=True)
class WalletFlowDisabledPolicyGuard:
    guard_status: str
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
    policy_guard_version: str
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
    guard_confirmation: str
    policy_checks: list[WalletFlowDisabledPolicyCheck]
    block_reasons: list[str]
    warnings: list[str]
    guard_rows: list[WalletFlowDisabledPolicyGuardRow]


@dataclass(frozen=True)
class WalletFlowDisabledPolicyGuardArtifacts:
    guard_md: Path
    guard_json: Path
    guard: WalletFlowDisabledPolicyGuard


def write_wallet_flow_disabled_policy_guard(
    *,
    disabled_chain_summary_json: Path,
    output_dir: Path,
) -> WalletFlowDisabledPolicyGuardArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    guard = build_wallet_flow_disabled_policy_guard(
        disabled_chain_summary_json=disabled_chain_summary_json
    )

    guard_md = output_dir / DISABLED_POLICY_GUARD_MD_FILENAME
    guard_json = output_dir / DISABLED_POLICY_GUARD_JSON_FILENAME
    guard_md.write_text(render_wallet_flow_disabled_policy_guard(guard))
    guard_json.write_text(_stable_json(_guard_json_payload(guard)) + "\n")

    return WalletFlowDisabledPolicyGuardArtifacts(
        guard_md=guard_md,
        guard_json=guard_json,
        guard=guard,
    )


def build_wallet_flow_disabled_policy_guard(
    *,
    disabled_chain_summary_json: Path,
) -> WalletFlowDisabledPolicyGuard:
    warnings: list[str] = []
    block_reasons: list[str] = []

    payload, state = _read_json_object(disabled_chain_summary_json)
    if state == "MISSING":
        chain_status = "MISSING"
        block_reasons.append("disabled_chain_summary_missing")
    elif state == "INVALID":
        chain_status = "INVALID"
        warnings.append(
            f"disabled_chain_summary_json_invalid path={disabled_chain_summary_json}"
        )
        block_reasons.append("disabled_chain_summary_invalid")
    else:
        chain_status = _payload_str(payload, "chain_status", default="unknown")

    contract_status = _payload_str(payload, "contract_status", default="unknown")
    receipt_status = _payload_str(payload, "receipt_status", default="unknown")
    adapter_status = _payload_str(payload, "adapter_status", default="unknown")
    run_status = _payload_str(payload, "run_status", default="unknown")
    ledger_status = _payload_str(payload, "ledger_status", default="unknown")
    decision = _normalize_decision(_payload_str(payload, "decision", default="unknown"))
    reviewer = _payload_str(payload, "reviewer", default="")
    review_note = _payload_str(payload, "review_note", default="")
    handoff_status = _payload_str(payload, "handoff_status", default="unknown")
    plan_status = _payload_str(payload, "plan_status", default="unknown")
    approved_packet_status = _payload_str(payload, "approved_packet_status", default="unknown")
    audit_status = _payload_str(payload, "audit_status", default="unknown")
    manifest_id = _payload_optional_str(payload, "manifest_id")
    manifest_rows = _payload_int(payload, "manifest_rows")
    planned_row_count = _payload_int(payload, "planned_row_count")

    policy_checks = _build_policy_checks(payload=payload, chain_state=state)
    failed_checks = [check.name for check in policy_checks if check.status == "FAIL"]
    block_reasons.extend(f"policy_check_failed:{name}" for name in failed_checks)

    any_awaiting = any(
        value == "AWAITING_APPROVAL"
        for value in (
            chain_status,
            contract_status,
            receipt_status,
            adapter_status,
            run_status,
        )
    )
    any_rejected = any(
        value == "REJECTED"
        for value in (
            chain_status,
            contract_status,
            receipt_status,
            adapter_status,
            run_status,
        )
    )

    required_checks_for_pass = {
        "chain_disabled_confirmed",
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
        "disabled_reason_policy",
        "chain_summary_version_expected",
        "chain_execution_mode_expected",
        "final_confirmation_present",
    }
    check_map = {check.name: check.status == "PASS" for check in policy_checks}
    policy_ready = all(check_map.get(name, False) for name in required_checks_for_pass)

    if state in {"MISSING", "INVALID"}:
        guard_status = "BLOCKED"
    elif policy_ready and chain_status == "DISABLED_CHAIN_CONFIRMED":
        guard_status = "POLICY_GUARD_PASS"
    elif any_rejected:
        guard_status = "REJECTED"
    elif any_awaiting:
        guard_status = "AWAITING_APPROVAL"
    else:
        guard_status = "BLOCKED"
        if not block_reasons:
            block_reasons.append("disabled_policy_guard_conditions_not_met")

    guard_rows = _build_guard_rows(payload=payload, guard_status=guard_status, limit=10)

    return WalletFlowDisabledPolicyGuard(
        guard_status=guard_status,
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
        policy_guard_version="wallet_flow_disabled_policy_guard_v1",
        execution_mode="disabled_policy_guard_only",
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
        guard_confirmation=GUARD_CONFIRMATION,
        policy_checks=policy_checks,
        block_reasons=sorted(set(block_reasons)),
        warnings=warnings,
        guard_rows=guard_rows,
    )


def render_wallet_flow_disabled_policy_guard(guard: WalletFlowDisabledPolicyGuard) -> str:
    lines = [
        "# Wallet Flow Disabled Policy Guard",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Disabled policy guard only.",
        "No ingestion executed.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Policy guard verifies disabled state only.",
        "Execution remains disabled by policy.",
        "",
        "## Guard Status",
        "",
        f"- guard_status: {guard.guard_status}",
        f"- chain_status: {guard.chain_status}",
        f"- contract_status: {guard.contract_status}",
        f"- receipt_status: {guard.receipt_status}",
        f"- adapter_status: {guard.adapter_status}",
        f"- run_status: {guard.run_status}",
        f"- ledger_status: {guard.ledger_status}",
        f"- decision: {guard.decision}",
        f"- reviewer: {guard.reviewer or '(none)'}",
        f"- review_note: {guard.review_note or '(none)'}",
        f"- handoff_status: {guard.handoff_status}",
        f"- plan_status: {guard.plan_status}",
        f"- approved_packet_status: {guard.approved_packet_status}",
        f"- audit_status: {guard.audit_status}",
        "",
        "## Summary",
        "",
        f"- manifest_id: {guard.manifest_id or '(missing)'}",
        f"- manifest_rows: {guard.manifest_rows}",
        f"- planned_row_count: {guard.planned_row_count}",
        f"- policy_guard_version: {guard.policy_guard_version}",
        f"- execution_mode: {guard.execution_mode}",
        f"- adapter_enabled: {guard.adapter_enabled}",
        f"- execution_enabled: {guard.execution_enabled}",
        f"- network_enabled: {guard.network_enabled}",
        f"- ingestion_enabled: {guard.ingestion_enabled}",
        f"- shell_enabled: {guard.shell_enabled}",
        f"- order_placement_enabled: {guard.order_placement_enabled}",
        f"- database_mutation_enabled: {guard.database_mutation_enabled}",
        f"- approval_required: {guard.approval_required}",
        f"- manual_operator_only: {guard.manual_operator_only}",
        f"- no_execution: {guard.no_execution}",
        f"- no_ingestion: {guard.no_ingestion}",
        f"- no_orders: {guard.no_orders}",
        f"- disabled_reason: {guard.disabled_reason}",
        f"- guard_confirmation: {guard.guard_confirmation}",
        "",
        "## Policy Checks",
        "",
        "| name | status | expected | actual | detail |",
        "|---|---|---|---|---|",
    ]
    for check in guard.policy_checks:
        lines.append(
            f"| {check.name} | {check.status} | {check.expected} | {check.actual} | {check.detail} |"
        )

    lines.extend(["", "## Guard Rows (First 10)", ""])
    if not guard.guard_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | contract_row_status | receipt_row_status | adapter_row_status | run_row_status | chain_row_status | idempotency_key | row_checksum | command | guard_row_status |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for row in guard.guard_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.contract_row_status} | {row.receipt_row_status} | "
                f"{row.adapter_row_status} | {row.run_row_status} | {row.chain_row_status} | "
                f"{row.idempotency_key} | {row.row_checksum} | {row.command} | {row.guard_row_status} |"
            )

    lines.extend(["", "## Block Reasons", ""])
    if guard.block_reasons:
        for reason in guard.block_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if guard.warnings:
        for warning in guard.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _build_policy_checks(
    *, payload: dict[str, object] | None, chain_state: str
) -> list[WalletFlowDisabledPolicyCheck]:
    if chain_state in {"MISSING", "INVALID"}:
        return [
            _check(
                name=name,
                expected="n/a",
                actual=chain_state.lower(),
                status="SKIP",
                detail="chain_summary_unavailable",
            )
            for name in (
                "chain_disabled_confirmed",
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
                "disabled_reason_policy",
                "chain_summary_version_expected",
                "chain_execution_mode_expected",
                "final_confirmation_present",
            )
        ]

    checks: list[WalletFlowDisabledPolicyCheck] = []
    checks.append(
        _expected_str_check(
            "chain_disabled_confirmed",
            _payload_str(payload, "chain_status", default="unknown"),
            "DISABLED_CHAIN_CONFIRMED",
        )
    )
    checks.append(
        _expected_str_check(
            "contract_ready",
            _payload_str(payload, "contract_status", default="unknown"),
            "CONTRACT_READY",
        )
    )
    checks.append(
        _expected_str_check(
            "receipt_ready",
            _payload_str(payload, "receipt_status", default="unknown"),
            "RECEIPT_READY",
        )
    )
    checks.append(
        _expected_str_check(
            "adapter_disabled_by_policy",
            _payload_str(payload, "adapter_status", default="unknown"),
            "DISABLED_BY_POLICY",
        )
    )
    checks.append(
        _expected_str_check(
            "run_disabled_confirmed",
            _payload_str(payload, "run_status", default="unknown"),
            "DISABLED_BY_POLICY_CONFIRMED",
        )
    )
    checks.append(_expected_bool_false_check("adapter_enabled_false", _payload_bool(payload, "adapter_enabled")))
    checks.append(
        _expected_bool_false_check("execution_enabled_false", _payload_bool(payload, "execution_enabled"))
    )
    checks.append(_expected_bool_false_check("network_enabled_false", _payload_bool(payload, "network_enabled")))
    checks.append(
        _expected_bool_false_check("ingestion_enabled_false", _payload_bool(payload, "ingestion_enabled"))
    )
    checks.append(_expected_bool_false_check("shell_enabled_false", _payload_bool(payload, "shell_enabled")))
    checks.append(
        _expected_bool_false_check(
            "order_placement_enabled_false", _payload_bool(payload, "order_placement_enabled")
        )
    )
    checks.append(
        _expected_bool_false_check(
            "database_mutation_enabled_false", _payload_bool(payload, "database_mutation_enabled")
        )
    )
    checks.append(_expected_bool_true_check("approval_required_true", _payload_bool(payload, "approval_required")))
    checks.append(
        _expected_bool_true_check("manual_operator_only_true", _payload_bool(payload, "manual_operator_only"))
    )
    checks.append(_expected_bool_true_check("no_execution_true", _payload_bool(payload, "no_execution")))
    checks.append(_expected_bool_true_check("no_ingestion_true", _payload_bool(payload, "no_ingestion")))
    checks.append(_expected_bool_true_check("no_orders_true", _payload_bool(payload, "no_orders")))
    checks.append(
        _expected_str_check(
            "disabled_reason_policy",
            _payload_str(payload, "disabled_reason", default=""),
            DISABLED_REASON,
        )
    )
    checks.append(
        _expected_str_check(
            "chain_summary_version_expected",
            _payload_str(payload, "chain_summary_version", default=""),
            "wallet_flow_disabled_chain_summary_v1",
        )
    )
    checks.append(
        _expected_str_check(
            "chain_execution_mode_expected",
            _payload_str(payload, "execution_mode", default=""),
            "disabled_chain_summary_only",
        )
    )
    checks.append(
        _presence_check(
            "final_confirmation_present",
            _payload_optional_str(payload, "final_confirmation"),
        )
    )
    return checks


def _build_guard_rows(
    *,
    payload: dict[str, object] | None,
    guard_status: str,
    limit: int,
) -> list[WalletFlowDisabledPolicyGuardRow]:
    rows_value = payload.get("chain_rows") if payload else None
    if not isinstance(rows_value, list):
        return []

    if guard_status == "POLICY_GUARD_PASS":
        row_status = "POLICY_GUARD_PASS"
    elif guard_status == "AWAITING_APPROVAL":
        row_status = "AWAITING_APPROVAL"
    elif guard_status == "REJECTED":
        row_status = "REJECTED"
    else:
        row_status = "BLOCKED"

    rows: list[WalletFlowDisabledPolicyGuardRow] = []
    for row in rows_value:
        if not isinstance(row, dict):
            continue
        if len(rows) >= limit:
            break
        rows.append(
            WalletFlowDisabledPolicyGuardRow(
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
                chain_row_status=_to_str(row.get("chain_row_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
                command=_to_str(row.get("command")),
                guard_row_status=row_status,
            )
        )
    return rows


def _guard_json_payload(guard: WalletFlowDisabledPolicyGuard) -> dict[str, object]:
    return {
        "guard_status": guard.guard_status,
        "chain_status": guard.chain_status,
        "contract_status": guard.contract_status,
        "receipt_status": guard.receipt_status,
        "adapter_status": guard.adapter_status,
        "run_status": guard.run_status,
        "ledger_status": guard.ledger_status,
        "decision": guard.decision,
        "reviewer": guard.reviewer,
        "review_note": guard.review_note,
        "handoff_status": guard.handoff_status,
        "plan_status": guard.plan_status,
        "approved_packet_status": guard.approved_packet_status,
        "audit_status": guard.audit_status,
        "manifest_id": guard.manifest_id,
        "manifest_rows": guard.manifest_rows,
        "planned_row_count": guard.planned_row_count,
        "policy_guard_version": guard.policy_guard_version,
        "execution_mode": guard.execution_mode,
        "adapter_enabled": guard.adapter_enabled,
        "execution_enabled": guard.execution_enabled,
        "network_enabled": guard.network_enabled,
        "ingestion_enabled": guard.ingestion_enabled,
        "shell_enabled": guard.shell_enabled,
        "order_placement_enabled": guard.order_placement_enabled,
        "database_mutation_enabled": guard.database_mutation_enabled,
        "approval_required": guard.approval_required,
        "manual_operator_only": guard.manual_operator_only,
        "no_execution": guard.no_execution,
        "no_ingestion": guard.no_ingestion,
        "no_orders": guard.no_orders,
        "disabled_reason": guard.disabled_reason,
        "guard_confirmation": guard.guard_confirmation,
        "policy_checks": [asdict(check) for check in guard.policy_checks],
        "block_reasons": guard.block_reasons,
        "warnings": guard.warnings,
        "guard_rows": [asdict(row) for row in guard.guard_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "disabled_policy_guard_only": True,
            "no_ingestion_executed": True,
            "no_manifest_commands_executed": True,
            "no_live_execution_adapter_enabled": True,
            "no_orders_placed": True,
            "policy_guard_verifies_disabled_state_only": True,
            "execution_remains_disabled_by_policy": True,
        },
    }


def _read_json_object(path: Path) -> tuple[dict[str, object] | None, str]:
    if not path.exists():
        return None, "MISSING"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, "INVALID"
    if not isinstance(data, dict):
        return None, "INVALID"
    return data, "OK"


def _expected_str_check(name: str, actual: str, expected: str) -> WalletFlowDisabledPolicyCheck:
    if actual == expected:
        return _check(name=name, expected=expected, actual=actual, status="PASS", detail=f"value={actual}")
    return _check(
        name=name,
        expected=expected,
        actual=actual,
        status="FAIL",
        detail=f"value={actual} expected={expected}",
    )


def _expected_bool_false_check(name: str, value: bool | None) -> WalletFlowDisabledPolicyCheck:
    if value is None:
        return _check(name=name, expected="false", actual="missing", status="FAIL", detail="value_missing")
    if value is False:
        return _check(name=name, expected="false", actual="false", status="PASS", detail="value=false")
    return _check(
        name=name, expected="false", actual="true", status="FAIL", detail="value=true expected=false"
    )


def _expected_bool_true_check(name: str, value: bool | None) -> WalletFlowDisabledPolicyCheck:
    if value is None:
        return _check(name=name, expected="true", actual="missing", status="FAIL", detail="value_missing")
    if value is True:
        return _check(name=name, expected="true", actual="true", status="PASS", detail="value=true")
    return _check(
        name=name, expected="true", actual="false", status="FAIL", detail="value=false expected=true"
    )


def _presence_check(name: str, value: str | None) -> WalletFlowDisabledPolicyCheck:
    if value:
        return _check(name=name, expected="present", actual="present", status="PASS", detail="value_present")
    return _check(name=name, expected="present", actual="missing", status="FAIL", detail="value_missing")


def _check(
    *, name: str, expected: str, actual: str, status: str, detail: str
) -> WalletFlowDisabledPolicyCheck:
    return WalletFlowDisabledPolicyCheck(
        name=name,
        status=status,
        expected=expected,
        actual=actual,
        detail=detail,
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


def _payload_bool(payload: dict[str, object] | None, key: str) -> bool | None:
    if payload is None:
        return None
    value = payload.get(key)
    if isinstance(value, bool):
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


def _normalize_decision(value: str) -> str:
    lowered = value.lower()
    if lowered in {"pending", "approve", "reject"}:
        return lowered
    return "unknown"


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
