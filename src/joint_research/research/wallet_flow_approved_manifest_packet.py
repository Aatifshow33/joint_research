"""Wallet-flow approved manifest export packet (review-only).

This module only reads manifest/review artifacts and writes export packet outputs.
It never executes ingestion or network calls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from joint_research.research.wallet_flow_manifest_review_gate import run_wallet_flow_manifest_review_gate

APPROVED_PACKET_MD_FILENAME = "wallet_flow_approved_manifest_packet.md"
APPROVED_PACKET_JSON_FILENAME = "wallet_flow_approved_manifest_packet.json"


@dataclass(frozen=True)
class WalletFlowApprovedManifestPreviewRow:
    batch_id: int
    rank: int
    asset: str
    market_id: str
    market_slug: str
    command_status: str
    idempotency_key: str
    row_checksum: str


@dataclass(frozen=True)
class WalletFlowApprovedManifestPacket:
    export_status: str
    gate_status: str
    manifest_id: str | None
    manifest_rows: int
    batch_count: int
    unique_idempotency_key_count: int
    unique_row_checksum_count: int
    dry_run: bool | None
    command_status_counts: list[tuple[str, int]]
    failure_reasons: list[str]
    review_gate_report_input: str
    review_gate_report_input_exists: bool
    preview_rows: list[WalletFlowApprovedManifestPreviewRow]


@dataclass(frozen=True)
class WalletFlowApprovedManifestPacketArtifacts:
    packet_md: Path
    packet_json: Path
    packet: WalletFlowApprovedManifestPacket


def write_wallet_flow_approved_manifest_packet(
    *,
    manifest_json: Path,
    review_gate_report: Path,
    output_dir: Path,
) -> WalletFlowApprovedManifestPacketArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = build_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json,
        review_gate_report=review_gate_report,
        output_dir=output_dir,
    )

    packet_md = output_dir / APPROVED_PACKET_MD_FILENAME
    packet_json = output_dir / APPROVED_PACKET_JSON_FILENAME
    packet_md.write_text(render_wallet_flow_approved_manifest_packet_md(packet))
    packet_json.write_text(_stable_json(_packet_json_payload(packet)) + "\n")

    return WalletFlowApprovedManifestPacketArtifacts(
        packet_md=packet_md,
        packet_json=packet_json,
        packet=packet,
    )


def build_wallet_flow_approved_manifest_packet(
    *,
    manifest_json: Path,
    review_gate_report: Path,
    output_dir: Path,
) -> WalletFlowApprovedManifestPacket:
    gate = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest_json,
        output_dir=output_dir,
        allow_review_required=False,
        require_dry_run=True,
    )

    payload = _read_manifest_payload(manifest_json)
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    rows = rows if isinstance(rows, list) else []

    manifest_id = payload.get("manifest_id") if isinstance(payload, dict) else None
    if not isinstance(manifest_id, str):
        manifest_id = None

    manifest_rows = _manifest_rows(payload, rows)
    batch_count = len(
        {
            int(row["batch_id"])
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("batch_id"), int)
        }
    )
    unique_idempotency_key_count = len(
        {
            str(row["idempotency_key"])
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("idempotency_key"), str)
            and row.get("idempotency_key")
        }
    )
    unique_row_checksum_count = len(
        {
            str(row["row_checksum"])
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("row_checksum"), str)
            and row.get("row_checksum")
        }
    )

    dry_run = payload.get("dry_run") if isinstance(payload, dict) else None
    if not isinstance(dry_run, bool):
        dry_run = None

    command_status_counts = _command_status_counts(rows)
    preview_rows = _preview_rows(rows, limit=10)

    gate_status = gate.status
    export_status = "PASS" if gate_status == "PASS" else "BLOCKED"
    failure_reasons = list(gate.failures) if gate_status != "PASS" else []

    return WalletFlowApprovedManifestPacket(
        export_status=export_status,
        gate_status=gate_status,
        manifest_id=manifest_id,
        manifest_rows=manifest_rows,
        batch_count=batch_count,
        unique_idempotency_key_count=unique_idempotency_key_count,
        unique_row_checksum_count=unique_row_checksum_count,
        dry_run=dry_run,
        command_status_counts=command_status_counts,
        failure_reasons=failure_reasons,
        review_gate_report_input=str(review_gate_report),
        review_gate_report_input_exists=review_gate_report.exists(),
        preview_rows=preview_rows,
    )


def render_wallet_flow_approved_manifest_packet_md(packet: WalletFlowApprovedManifestPacket) -> str:
    lines = [
        "# Wallet Flow Approved Manifest Export Packet",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "No ingestion executed.",
        "Approved for human review only.",
        "",
        "## Export Status",
        "",
        f"- export_status: {packet.export_status}",
        f"- gate_status: {packet.gate_status}",
        "",
        "## Manifest Summary",
        "",
        f"- manifest_id: {packet.manifest_id or '(missing)'}",
        f"- manifest_rows: {packet.manifest_rows}",
        f"- batch_count: {packet.batch_count}",
        f"- unique_idempotency_key_count: {packet.unique_idempotency_key_count}",
        f"- unique_row_checksum_count: {packet.unique_row_checksum_count}",
        f"- dry_run: {packet.dry_run}",
        f"- review_gate_report_input: {packet.review_gate_report_input}",
        f"- review_gate_report_input_exists: {packet.review_gate_report_input_exists}",
        "",
        "## Command Status Counts",
        "",
    ]

    if packet.command_status_counts:
        for status, count in packet.command_status_counts:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Preview Rows (First 10)", ""])
    if not packet.preview_rows:
        lines.append("(none)")
    else:
        lines.append(
            "| batch_id | rank | asset | market_id | market_slug | command_status | idempotency_key | row_checksum |"
        )
        lines.append("|---:|---:|---|---|---|---|---|---|")
        for row in packet.preview_rows:
            lines.append(
                f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_id} | {row.market_slug} | "
                f"{row.command_status} | {row.idempotency_key} | {row.row_checksum} |"
            )

    lines.extend(["", "## Gate Failures", ""])
    if packet.failure_reasons:
        for reason in packet.failure_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _packet_json_payload(packet: WalletFlowApprovedManifestPacket) -> dict[str, object]:
    return {
        "export_status": packet.export_status,
        "gate_status": packet.gate_status,
        "manifest_id": packet.manifest_id,
        "manifest_rows": packet.manifest_rows,
        "batch_count": packet.batch_count,
        "unique_idempotency_key_count": packet.unique_idempotency_key_count,
        "unique_row_checksum_count": packet.unique_row_checksum_count,
        "dry_run": packet.dry_run,
        "command_status_counts": [
            {"command_status": status, "count": count}
            for status, count in packet.command_status_counts
        ],
        "failure_reasons": packet.failure_reasons,
        "review_gate_report_input": packet.review_gate_report_input,
        "review_gate_report_input_exists": packet.review_gate_report_input_exists,
        "preview_rows": [asdict(row) for row in packet.preview_rows],
        "safety": {
            "exploratory_only": True,
            "not_tradeable": True,
            "no_candidates_promoted": True,
            "no_threshold_changes": True,
            "no_live_trading_changes": True,
            "no_ingestion_executed": True,
            "approved_for_human_review_only": True,
        },
    }


def _manifest_rows(payload: dict[str, object] | None, rows: list[object]) -> int:
    if isinstance(payload, dict):
        declared = payload.get("manifest_rows")
        if isinstance(declared, int):
            return declared
    return len(rows)


def _command_status_counts(rows: list[object]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = row.get("command_status")
        if not isinstance(status, str) or not status:
            status = "(missing)"
        counts[status] = counts.get(status, 0) + 1
    return sorted(counts.items(), key=lambda item: (item[0], item[1]))


def _preview_rows(rows: list[object], *, limit: int) -> list[WalletFlowApprovedManifestPreviewRow]:
    preview: list[WalletFlowApprovedManifestPreviewRow] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if len(preview) >= limit:
            break
        preview.append(
            WalletFlowApprovedManifestPreviewRow(
                batch_id=_to_int(row.get("batch_id")),
                rank=_to_int(row.get("rank")),
                asset=_to_str(row.get("asset")),
                market_id=_to_str(row.get("market_id")),
                market_slug=_to_str(row.get("market_slug")),
                command_status=_to_str(row.get("command_status")),
                idempotency_key=_to_str(row.get("idempotency_key")),
                row_checksum=_to_str(row.get("row_checksum")),
            )
        )
    return preview


def _read_manifest_payload(manifest_json: Path) -> dict[str, object] | None:
    if not manifest_json.exists():
        return None
    try:
        payload = json.loads(manifest_json.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


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
