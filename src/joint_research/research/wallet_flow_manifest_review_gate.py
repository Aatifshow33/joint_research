"""Wallet-flow manifest review gate (validation only).

This module reads a previously-generated execution manifest JSON and performs
deterministic safety validations. It never executes ingestion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REVIEW_GATE_MD_FILENAME = "wallet_flow_manifest_review_gate.md"

_UNSAFE_OPERATOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r";"),
    re.compile(r"&&"),
    re.compile(r"\|\|"),
    re.compile(r"`"),
    re.compile(r"\$\("),
    re.compile(r">"),
    re.compile(r"<"),
    re.compile(r"\|"),
)


@dataclass(frozen=True)
class WalletFlowManifestReviewGateResult:
    status: str  # PASS|FAIL
    manifest_rows: int
    failures: list[str]
    warnings: list[str]
    report_path: Path | None


def run_wallet_flow_manifest_review_gate(
    *,
    manifest_json: Path,
    output_dir: Path,
    allow_review_required: bool = False,
    require_dry_run: bool = True,
) -> WalletFlowManifestReviewGateResult:
    failures: list[str] = []
    warnings: list[str] = []

    if not manifest_json.exists():
        failures.append(f"manifest_json_missing path={manifest_json}")
        result = WalletFlowManifestReviewGateResult(
            status="FAIL",
            manifest_rows=0,
            failures=failures,
            warnings=warnings,
            report_path=None,
        )
        return _write_report(output_dir=output_dir, manifest_json=manifest_json, result=result)

    try:
        payload = json.loads(manifest_json.read_text())
    except json.JSONDecodeError as exc:
        failures.append(f"invalid_json error={exc}")
        result = WalletFlowManifestReviewGateResult(
            status="FAIL",
            manifest_rows=0,
            failures=failures,
            warnings=warnings,
            report_path=None,
        )
        return _write_report(output_dir=output_dir, manifest_json=manifest_json, result=result)

    required_keys = {"manifest_id", "dry_run", "batch_size", "max_batches", "rows", "thresholds"}
    missing = sorted(k for k in required_keys if k not in payload)
    if missing:
        failures.append("missing_manifest_keys=" + ",".join(missing))

    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        failures.append("rows_not_a_list")
        rows = []

    declared_rows = payload.get("manifest_rows")
    if declared_rows is None:
        failures.append("manifest_rows_missing")
    else:
        if not isinstance(declared_rows, int):
            failures.append("manifest_rows_not_int")
        elif declared_rows != len(rows):
            failures.append(f"manifest_rows_mismatch declared={declared_rows} actual={len(rows)}")

    dry_run = payload.get("dry_run")
    if require_dry_run and dry_run is not True:
        failures.append(f"dry_run_required require_dry_run={require_dry_run} dry_run={dry_run}")

    idempotency_keys: set[str] = set()
    row_checksums: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"row_not_object index={i}")
            continue

        batch_id = row.get("batch_id")
        rank = row.get("rank")
        if not isinstance(batch_id, int) or batch_id <= 0:
            failures.append(f"invalid_batch_id index={i} batch_id={batch_id}")
        if not isinstance(rank, int) or rank <= 0:
            failures.append(f"invalid_rank index={i} rank={rank}")

        idem = row.get("idempotency_key")
        if not isinstance(idem, str) or not idem.strip():
            failures.append(f"missing_idempotency_key index={i}")
        else:
            if idem in idempotency_keys:
                failures.append(f"duplicate_idempotency_key key={idem}")
            idempotency_keys.add(idem)

        checksum = row.get("row_checksum")
        if not isinstance(checksum, str) or not checksum.strip():
            failures.append(f"missing_row_checksum index={i}")
        else:
            if checksum in row_checksums:
                failures.append(f"duplicate_row_checksum checksum={checksum}")
            row_checksums.add(checksum)

        command_status = row.get("command_status")
        if command_status not in {"REVIEW_REQUIRED", "REVIEW_READY"}:
            failures.append(f"invalid_command_status index={i} status={command_status}")
        if command_status == "REVIEW_REQUIRED" and not allow_review_required:
            failures.append("review_required_not_allowed")

        ingest_command = row.get("ingest_command")
        if not isinstance(ingest_command, str) or not ingest_command.strip():
            failures.append(f"missing_ingest_command index={i}")
        else:
            unsafe = _detect_unsafe_operators(ingest_command)
            if unsafe:
                failures.append(
                    f"unsafe_ingest_command index={i} operator={unsafe} ingest_command={ingest_command}"
                )

    # Safety copy equivalence: ensure metadata exists (we can't require the MD contents).
    if "manifest_id" not in payload or "thresholds" not in payload:
        failures.append("missing_safety_metadata")

    status = "PASS" if not failures else "FAIL"
    result = WalletFlowManifestReviewGateResult(
        status=status,
        manifest_rows=len(rows),
        failures=failures,
        warnings=warnings,
        report_path=None,
    )
    return _write_report(output_dir=output_dir, manifest_json=manifest_json, result=result)


def _detect_unsafe_operators(command: str) -> str | None:
    for pattern in _UNSAFE_OPERATOR_PATTERNS:
        if pattern.search(command):
            return pattern.pattern
    return None


def _write_report(
    *,
    output_dir: Path,
    manifest_json: Path,
    result: WalletFlowManifestReviewGateResult,
) -> WalletFlowManifestReviewGateResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / REVIEW_GATE_MD_FILENAME

    lines = [
        "# Wallet Flow Manifest Review Gate",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Review gate only.",
        "No ingestion executed.",
        "",
        "## Inputs",
        "",
        f"- manifest_json: {manifest_json}",
        "",
        "## Result",
        "",
        f"- gate_status: {result.status}",
        f"- manifest_rows: {result.manifest_rows}",
        f"- failures: {len(result.failures)}",
        f"- warnings: {len(result.warnings)}",
        "",
    ]
    if result.failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in result.failures)
        lines.append("")
    if result.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")

    report_path.write_text("\n".join(lines).rstrip() + "\n")
    return WalletFlowManifestReviewGateResult(
        status=result.status,
        manifest_rows=result.manifest_rows,
        failures=result.failures,
        warnings=result.warnings,
        report_path=report_path,
    )

