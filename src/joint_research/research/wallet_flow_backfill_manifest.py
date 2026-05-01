"""Wallet-flow backfill execution manifest (review-only).

This module is exploratory-only. It produces deterministic review artifacts and
never executes ingestion or network calls.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from joint_research.research.wallet_flow_backfill_batches import (
    WalletFlowBackfillBatchesPlan,
    run_wallet_flow_backfill_batches_plan,
)
from joint_research.research.wallet_flow_backfill_priority import (
    WalletFlowBackfillPriorityThresholds,
)

MANIFEST_MD_FILENAME = "wallet_flow_backfill_execution_manifest.md"
MANIFEST_CSV_FILENAME = "wallet_flow_backfill_execution_manifest.csv"
MANIFEST_JSON_FILENAME = "wallet_flow_backfill_execution_manifest.json"


@dataclass(frozen=True)
class WalletFlowBackfillManifestRow:
    manifest_id: str
    batch_id: int
    rank: int
    idempotency_key: str
    market_id: str
    market_slug: str
    asset: str
    is_active: bool
    priority_score: str
    reasons: str
    action: str
    command_status: str
    ingest_command: str
    row_checksum: str


@dataclass(frozen=True)
class WalletFlowBackfillManifestPlan:
    coverage_csv: Path
    thresholds: WalletFlowBackfillPriorityThresholds
    batch_size: int
    max_batches: int
    dry_run: bool
    command_template: str | None
    manifest_id: str
    rows: list[WalletFlowBackfillManifestRow]
    batches: int


def run_wallet_flow_backfill_manifest_plan(
    *,
    coverage_csv: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    batch_size: int = 25,
    max_batches: int = 5,
    dry_run: bool = True,
    command_template: str | None = None,
) -> WalletFlowBackfillManifestPlan:
    batches_plan: WalletFlowBackfillBatchesPlan = run_wallet_flow_backfill_batches_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
    )

    draft_rows: list[dict[str, object]] = []
    for idx, priority in enumerate(batches_plan.rows):
        batch_id = (idx // max(1, batch_size)) + 1
        idempotency_key = _idempotency_key(
            market_id=priority.market_id,
            batch_id=batch_id,
            rank=priority.rank,
        )
        command_status, ingest_command = _resolve_ingest_command(
            market_id=priority.market_id,
            market_slug=priority.market_slug,
            asset=priority.asset,
            batch_id=batch_id,
            rank=priority.rank,
            command_template=command_template,
        )
        draft_rows.append(
            {
                "batch_id": batch_id,
                "rank": priority.rank,
                "idempotency_key": idempotency_key,
                "market_id": priority.market_id,
                "market_slug": priority.market_slug,
                "asset": priority.asset,
                "is_active": priority.is_active,
                "priority_score": f"{priority.priority_score:.4f}",
                "reasons": ";".join(priority.reasons),
                "action": priority.action,
                "command_status": command_status,
                "ingest_command": ingest_command,
            }
        )

    manifest_id = _manifest_id(
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
        command_template=command_template,
        rows=draft_rows,
    )

    rows: list[WalletFlowBackfillManifestRow] = []
    for payload in draft_rows:
        row_payload = {
            "manifest_id": manifest_id,
            **payload,
        }
        row_checksum = _row_checksum(row_payload)
        rows.append(
            WalletFlowBackfillManifestRow(
                manifest_id=manifest_id,
                batch_id=int(payload["batch_id"]),
                rank=int(payload["rank"]),
                idempotency_key=str(payload["idempotency_key"]),
                market_id=str(payload["market_id"]),
                market_slug=str(payload["market_slug"]),
                asset=str(payload["asset"]),
                is_active=bool(payload["is_active"]),
                priority_score=str(payload["priority_score"]),
                reasons=str(payload["reasons"]),
                action=str(payload["action"]),
                command_status=str(payload["command_status"]),
                ingest_command=str(payload["ingest_command"]),
                row_checksum=row_checksum,
            )
        )

    batches = len(batches_plan.batches)
    return WalletFlowBackfillManifestPlan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
        command_template=command_template,
        manifest_id=manifest_id,
        rows=rows,
        batches=batches,
    )


def write_wallet_flow_backfill_manifest_artifacts(
    *,
    coverage_csv: Path,
    output_dir: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    batch_size: int = 25,
    max_batches: int = 5,
    dry_run: bool = True,
    command_template: str | None = None,
) -> tuple[Path, Path, Path, WalletFlowBackfillManifestPlan]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = run_wallet_flow_backfill_manifest_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
        command_template=command_template,
    )

    report_path = output_dir / MANIFEST_MD_FILENAME
    csv_path = output_dir / MANIFEST_CSV_FILENAME
    json_path = output_dir / MANIFEST_JSON_FILENAME
    report_path.write_text(render_wallet_flow_backfill_manifest_report(plan))
    _write_manifest_csv(csv_path, plan.rows)
    _write_manifest_json(json_path, plan)
    return report_path, csv_path, json_path, plan


def render_wallet_flow_backfill_manifest_report(plan: WalletFlowBackfillManifestPlan) -> str:
    lines = [
        "# Wallet Flow Backfill Execution Manifest",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Manifest generation only.",
        "No ingestion executed.",
        "",
        "## Summary",
        "",
        f"- manifest_id: {plan.manifest_id}",
        f"- coverage_csv: {plan.coverage_csv}",
        f"- dry_run: {plan.dry_run}",
        f"- batch_size: {plan.batch_size}",
        f"- max_batches: {plan.max_batches}",
        f"- batches: {plan.batches}",
        f"- manifest_rows: {len(plan.rows)}",
        "",
        "## Thresholds",
        "",
        f"- min_wallet_flow_rows: {plan.thresholds.min_wallet_flow_rows}",
        f"- min_market_flow_hourly_rows: {plan.thresholds.min_market_flow_hourly_rows}",
        f"- min_whale_flow_hourly_rows: {plan.thresholds.min_whale_flow_hourly_rows}",
        "",
    ]
    if plan.command_template is not None:
        lines.extend(["## Command Template", "", f"- template: `{plan.command_template}`", ""])
    else:
        lines.extend(["## Command Template", "", "- template: (none)", ""])

    lines.extend(
        [
            "## Rows",
            "",
            "| batch_id | rank | asset | market_slug | is_active | priority_score | command_status | idempotency_key | row_checksum |",
            "|---:|---:|---|---|---|---:|---|---|---|",
        ]
    )
    for row in plan.rows:
        lines.append(
            f"| {row.batch_id} | {row.rank} | {row.asset} | {row.market_slug} | "
            f"{row.is_active} | {row.priority_score} | {row.command_status} | "
            f"{row.idempotency_key} | {row.row_checksum} |"
        )

    return "\n".join(lines).rstrip() + "\n"


def _idempotency_key(*, market_id: str, batch_id: int, rank: int) -> str:
    return f"wallet_flow_backfill:{market_id}:batch={batch_id}:rank={rank}"


def _resolve_ingest_command(
    *,
    market_id: str,
    market_slug: str,
    asset: str,
    batch_id: int,
    rank: int,
    command_template: str | None,
) -> tuple[str, str]:
    if command_template is None:
        return (
            "REVIEW_REQUIRED",
            f"REVIEW_REQUIRED: no existing wallet-flow ingest command found for market_id={market_id}",
        )
    rendered = command_template.format(
        market_id=market_id,
        market_slug=market_slug,
        asset=asset,
        batch_id=batch_id,
        rank=rank,
    )
    return ("REVIEW_READY", rendered)


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _manifest_id(
    *,
    thresholds: WalletFlowBackfillPriorityThresholds,
    batch_size: int,
    max_batches: int,
    dry_run: bool,
    command_template: str | None,
    rows: list[dict[str, object]],
) -> str:
    payload = {
        "thresholds": asdict(thresholds),
        "batch_size": batch_size,
        "max_batches": max_batches,
        "dry_run": dry_run,
        "command_template": command_template,
        "rows": rows,
    }
    return _sha256_hex(_stable_json(payload))


def _row_checksum(row_payload: dict[str, object]) -> str:
    return _sha256_hex(_stable_json(row_payload))


def _write_manifest_csv(path: Path, rows: list[WalletFlowBackfillManifestRow]) -> None:
    fieldnames = [
        "manifest_id",
        "batch_id",
        "rank",
        "idempotency_key",
        "market_id",
        "market_slug",
        "asset",
        "is_active",
        "priority_score",
        "reasons",
        "action",
        "command_status",
        "ingest_command",
        "row_checksum",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_manifest_json(path: Path, plan: WalletFlowBackfillManifestPlan) -> None:
    payload = {
        "manifest_id": plan.manifest_id,
        "coverage_csv": str(plan.coverage_csv),
        "dry_run": plan.dry_run,
        "batch_size": plan.batch_size,
        "max_batches": plan.max_batches,
        "batches": plan.batches,
        "manifest_rows": len(plan.rows),
        "thresholds": asdict(plan.thresholds),
        "command_template": plan.command_template,
        "rows": [asdict(row) for row in plan.rows],
    }
    path.write_text(_stable_json(payload) + "\n")

