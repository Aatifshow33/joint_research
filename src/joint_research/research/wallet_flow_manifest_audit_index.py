"""Wallet-flow manifest audit index (review-only).

This module summarizes the wallet-flow backfill review chain without executing
any ingestion or network operations.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

AUDIT_INDEX_MD_FILENAME = "wallet_flow_manifest_audit_index.md"
AUDIT_INDEX_JSON_FILENAME = "wallet_flow_manifest_audit_index.json"


@dataclass(frozen=True)
class WalletFlowManifestAuditReportRecord:
    report_name: str
    path: str
    exists: bool
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True)
class WalletFlowManifestJsonSummary:
    manifest_id: str | None
    manifest_rows: int
    dry_run: bool | None
    command_status_counts: list[tuple[str, int]]
    unique_idempotency_keys: int
    unique_row_checksums: int


@dataclass(frozen=True)
class WalletFlowApprovedPacketJsonSummary:
    export_status: str | None
    gate_status: str | None
    manifest_rows: int | None


@dataclass(frozen=True)
class WalletFlowManifestAuditIndex:
    audit_status: str
    reports_found: int
    reports_missing: int
    recommendation: str
    reports: list[WalletFlowManifestAuditReportRecord]
    warnings: list[str]
    manifest_json_summary: WalletFlowManifestJsonSummary | None
    approved_packet_json_summary: WalletFlowApprovedPacketJsonSummary | None


@dataclass(frozen=True)
class WalletFlowManifestAuditIndexArtifacts:
    audit_index_md: Path
    audit_index_json: Path
    index: WalletFlowManifestAuditIndex


def write_wallet_flow_manifest_audit_index(
    *,
    output_dir: Path,
    coverage_gate_report: Path,
    priority_report: Path,
    batch_report: Path,
    manifest_report: Path,
    review_gate_report: Path,
    approved_packet_report: Path,
    manifest_json: Path,
    approved_packet_json: Path,
) -> WalletFlowManifestAuditIndexArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    index = build_wallet_flow_manifest_audit_index(
        coverage_gate_report=coverage_gate_report,
        priority_report=priority_report,
        batch_report=batch_report,
        manifest_report=manifest_report,
        review_gate_report=review_gate_report,
        approved_packet_report=approved_packet_report,
        manifest_json=manifest_json,
        approved_packet_json=approved_packet_json,
    )

    audit_index_md = output_dir / AUDIT_INDEX_MD_FILENAME
    audit_index_json = output_dir / AUDIT_INDEX_JSON_FILENAME
    audit_index_md.write_text(render_wallet_flow_manifest_audit_index(index))
    audit_index_json.write_text(_stable_json(_index_json_payload(index)) + "\n")

    return WalletFlowManifestAuditIndexArtifacts(
        audit_index_md=audit_index_md,
        audit_index_json=audit_index_json,
        index=index,
    )


def build_wallet_flow_manifest_audit_index(
    *,
    coverage_gate_report: Path,
    priority_report: Path,
    batch_report: Path,
    manifest_report: Path,
    review_gate_report: Path,
    approved_packet_report: Path,
    manifest_json: Path,
    approved_packet_json: Path,
) -> WalletFlowManifestAuditIndex:
    expected_reports = [
        ("coverage_gate_report", coverage_gate_report),
        ("priority_report", priority_report),
        ("batch_report", batch_report),
        ("manifest_report", manifest_report),
        ("review_gate_report", review_gate_report),
        ("approved_packet_report", approved_packet_report),
        ("manifest_json", manifest_json),
        ("approved_packet_json", approved_packet_json),
    ]

    report_records = [
        _report_record(report_name=name, path=path)
        for name, path in expected_reports
    ]

    warnings: list[str] = []
    manifest_summary = _load_manifest_json_summary(manifest_json, warnings)
    approved_packet_summary = _load_approved_packet_json_summary(approved_packet_json, warnings)

    if approved_packet_summary is not None and approved_packet_summary.export_status == "PASS":
        audit_status = "READY"
        recommendation = "Ready for human review of approved packet."
    else:
        audit_status = "BLOCKED"
        recommendation = "Blocked until approved packet export_status=PASS."

    reports_found = sum(1 for report in report_records if report.exists)
    reports_missing = len(report_records) - reports_found

    return WalletFlowManifestAuditIndex(
        audit_status=audit_status,
        reports_found=reports_found,
        reports_missing=reports_missing,
        recommendation=recommendation,
        reports=report_records,
        warnings=warnings,
        manifest_json_summary=manifest_summary,
        approved_packet_json_summary=approved_packet_summary,
    )


def render_wallet_flow_manifest_audit_index(index: WalletFlowManifestAuditIndex) -> str:
    lines = [
        "# Wallet Flow Manifest Audit Index",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Audit index only.",
        "No ingestion executed.",
        "",
        "## Audit Status",
        "",
        f"- audit_status: {index.audit_status}",
        f"- reports_found: {index.reports_found}",
        f"- reports_missing: {index.reports_missing}",
        f"- recommendation: {index.recommendation}",
        "",
        "## Report Inventory",
        "",
        "| report_name | path | exists | size_bytes | sha256 |",
        "|---|---|---|---:|---|",
    ]

    for record in index.reports:
        lines.append(
            f"| {record.report_name} | {record.path} | {record.exists} | "
            f"{record.size_bytes if record.size_bytes is not None else ''} | "
            f"{record.sha256 or ''} |"
        )

    lines.extend(["", "## Manifest JSON Summary", ""])
    if index.manifest_json_summary is None:
        lines.append("- (unavailable)")
    else:
        summary = index.manifest_json_summary
        lines.extend(
            [
                f"- manifest_id: {summary.manifest_id or '(missing)'}",
                f"- manifest_rows: {summary.manifest_rows}",
                f"- dry_run: {summary.dry_run}",
                f"- unique_idempotency_keys: {summary.unique_idempotency_keys}",
                f"- unique_row_checksums: {summary.unique_row_checksums}",
                "- command_status_counts:",
            ]
        )
        if summary.command_status_counts:
            for status, count in summary.command_status_counts:
                lines.append(f"  - {status}: {count}")
        else:
            lines.append("  - (none)")

    lines.extend(["", "## Approved Packet JSON Summary", ""])
    if index.approved_packet_json_summary is None:
        lines.append("- (unavailable)")
    else:
        approved = index.approved_packet_json_summary
        lines.extend(
            [
                f"- export_status: {approved.export_status}",
                f"- gate_status: {approved.gate_status}",
                f"- manifest_rows: {approved.manifest_rows}",
            ]
        )

    lines.extend(["", "## Warnings", ""])
    if index.warnings:
        for warning in index.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _report_record(*, report_name: str, path: Path) -> WalletFlowManifestAuditReportRecord:
    if not path.exists():
        return WalletFlowManifestAuditReportRecord(
            report_name=report_name,
            path=str(path),
            exists=False,
            size_bytes=None,
            sha256=None,
        )
    data = path.read_bytes()
    return WalletFlowManifestAuditReportRecord(
        report_name=report_name,
        path=str(path),
        exists=True,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _load_manifest_json_summary(
    manifest_json: Path,
    warnings: list[str],
) -> WalletFlowManifestJsonSummary | None:
    payload = _read_json_object(manifest_json, warnings, label="manifest_json")
    if payload is None:
        return None

    rows = payload.get("rows")
    if not isinstance(rows, list):
        rows = []

    manifest_rows = payload.get("manifest_rows")
    if not isinstance(manifest_rows, int):
        manifest_rows = len(rows)

    dry_run = payload.get("dry_run")
    if not isinstance(dry_run, bool):
        dry_run = None

    manifest_id = payload.get("manifest_id")
    if not isinstance(manifest_id, str):
        manifest_id = None

    command_status_counts = _manifest_command_status_counts(rows)
    unique_idempotency_keys = len(
        {
            str(row.get("idempotency_key"))
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("idempotency_key"), str)
            and row.get("idempotency_key")
        }
    )
    unique_row_checksums = len(
        {
            str(row.get("row_checksum"))
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("row_checksum"), str)
            and row.get("row_checksum")
        }
    )

    return WalletFlowManifestJsonSummary(
        manifest_id=manifest_id,
        manifest_rows=manifest_rows,
        dry_run=dry_run,
        command_status_counts=command_status_counts,
        unique_idempotency_keys=unique_idempotency_keys,
        unique_row_checksums=unique_row_checksums,
    )


def _load_approved_packet_json_summary(
    approved_packet_json: Path,
    warnings: list[str],
) -> WalletFlowApprovedPacketJsonSummary | None:
    payload = _read_json_object(approved_packet_json, warnings, label="approved_packet_json")
    if payload is None:
        return None

    export_status = payload.get("export_status")
    if not isinstance(export_status, str):
        export_status = None

    gate_status = payload.get("gate_status")
    if not isinstance(gate_status, str):
        gate_status = None

    manifest_rows = payload.get("manifest_rows")
    if not isinstance(manifest_rows, int):
        manifest_rows = None

    return WalletFlowApprovedPacketJsonSummary(
        export_status=export_status,
        gate_status=gate_status,
        manifest_rows=manifest_rows,
    )


def _manifest_command_status_counts(rows: list[object]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = row.get("command_status")
        if not isinstance(status, str) or not status:
            status = "(missing)"
        counts[status] = counts.get(status, 0) + 1
    return sorted(counts.items(), key=lambda item: item[0])


def _read_json_object(path: Path, warnings: list[str], *, label: str) -> dict[str, object] | None:
    if not path.exists():
        warnings.append(f"{label}_missing path={path}")
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        warnings.append(f"{label}_invalid_json path={path} error={exc}")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"{label}_not_object path={path}")
        return None
    return payload


def _index_json_payload(index: WalletFlowManifestAuditIndex) -> dict[str, object]:
    return {
        "audit_status": index.audit_status,
        "reports_found": index.reports_found,
        "reports_missing": index.reports_missing,
        "recommendation": index.recommendation,
        "reports": [asdict(report) for report in index.reports],
        "warnings": index.warnings,
        "manifest_json_summary": asdict(index.manifest_json_summary)
        if index.manifest_json_summary is not None
        else None,
        "approved_packet_json_summary": asdict(index.approved_packet_json_summary)
        if index.approved_packet_json_summary is not None
        else None,
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "audit_index_only": True,
            "no_ingestion_executed": True,
        },
    }


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
