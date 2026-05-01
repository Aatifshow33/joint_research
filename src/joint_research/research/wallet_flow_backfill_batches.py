"""Wallet-flow backfill batch planner.

This module is exploratory-only. It generates deterministic batches that can be
used to *plan* safe ingestion work, but it must not execute ingestion.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from joint_research.research.wallet_flow_backfill_priority import (
    WalletFlowBackfillPriority,
    WalletFlowBackfillPriorityPlan,
    WalletFlowBackfillPriorityThresholds,
    run_wallet_flow_backfill_priority_plan,
)

BACKFILL_BATCHES_MD_FILENAME = "wallet_flow_backfill_batches.md"
BACKFILL_BATCHES_CSV_FILENAME = "wallet_flow_backfill_batches.csv"


@dataclass(frozen=True)
class WalletFlowBackfillBatchSummary:
    batch_id: int
    batch_rank_start: int
    batch_rank_end: int
    market_count: int
    active_market_count: int
    total_priority_score: float
    action: str


@dataclass(frozen=True)
class WalletFlowBackfillBatchesPlan:
    coverage_csv: Path
    thresholds: WalletFlowBackfillPriorityThresholds
    dry_run: bool
    batch_size: int
    max_batches: int
    batches: list[WalletFlowBackfillBatchSummary]
    rows: list[WalletFlowBackfillPriority]


def run_wallet_flow_backfill_batches_plan(
    *,
    coverage_csv: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    batch_size: int = 25,
    max_batches: int = 5,
    dry_run: bool = True,
) -> WalletFlowBackfillBatchesPlan:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if max_batches <= 0:
        raise ValueError("max_batches must be positive")

    top_limit = batch_size * max_batches
    priority_plan: WalletFlowBackfillPriorityPlan = run_wallet_flow_backfill_priority_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        top_limit=top_limit,
    )
    rows = priority_plan.priorities

    batches: list[WalletFlowBackfillBatchSummary] = []
    for batch_index in range(max_batches):
        start = batch_index * batch_size
        end = start + batch_size
        chunk = rows[start:end]
        if not chunk:
            break
        batches.append(_summarize_batch(batch_id=batch_index + 1, rows=chunk))

    planned_rows = [row for batch in batches for row in _rows_for_batch(rows, batch, batch_size)]
    return WalletFlowBackfillBatchesPlan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        dry_run=dry_run,
        batch_size=batch_size,
        max_batches=max_batches,
        batches=batches,
        rows=planned_rows,
    )


def write_wallet_flow_backfill_batches_artifacts(
    *,
    coverage_csv: Path,
    output_dir: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    batch_size: int = 25,
    max_batches: int = 5,
    dry_run: bool = True,
) -> tuple[Path, Path, WalletFlowBackfillBatchesPlan]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = run_wallet_flow_backfill_batches_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
    )
    report_path = output_dir / BACKFILL_BATCHES_MD_FILENAME
    csv_path = output_dir / BACKFILL_BATCHES_CSV_FILENAME
    report_path.write_text(render_wallet_flow_backfill_batches_report(plan))
    _write_batches_csv(csv_path, plan.rows, batch_size=plan.batch_size)
    return report_path, csv_path, plan


def render_wallet_flow_backfill_batches_report(plan: WalletFlowBackfillBatchesPlan) -> str:
    lines = [
        "# Wallet Flow Backfill Batches",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "Dry-run planning only.",
        "",
        "## Summary",
        "",
        f"- coverage_csv: {plan.coverage_csv}",
        f"- dry_run: {plan.dry_run}",
        f"- batch_size: {plan.batch_size}",
        f"- max_batches: {plan.max_batches}",
        f"- batches: {len(plan.batches)}",
        f"- markets_planned: {len(plan.rows)}",
        "",
        "## Thresholds",
        "",
        f"- min_wallet_flow_rows: {plan.thresholds.min_wallet_flow_rows}",
        f"- min_market_flow_hourly_rows: {plan.thresholds.min_market_flow_hourly_rows}",
        f"- min_whale_flow_hourly_rows: {plan.thresholds.min_whale_flow_hourly_rows}",
        "",
        "## Batch Summaries",
        "",
    ]
    lines.extend(_render_batch_summary_table(plan.batches))
    lines.extend(
        [
            "",
            "## Batch Rows",
            "",
        ]
    )
    lines.extend(_render_batch_rows_table(plan.rows, plan.batch_size))
    return "\n".join(lines).rstrip() + "\n"


def _summarize_batch(*, batch_id: int, rows: list[WalletFlowBackfillPriority]) -> WalletFlowBackfillBatchSummary:
    action = _dominant_action(rows)
    total_priority_score = sum(r.priority_score for r in rows)
    active_market_count = sum(1 for r in rows if r.is_active)
    return WalletFlowBackfillBatchSummary(
        batch_id=batch_id,
        batch_rank_start=rows[0].rank,
        batch_rank_end=rows[-1].rank,
        market_count=len(rows),
        active_market_count=active_market_count,
        total_priority_score=total_priority_score,
        action=action,
    )


def _dominant_action(rows: list[WalletFlowBackfillPriority]) -> str:
    if not rows:
        return "mixed"
    counts = Counter(r.action for r in rows)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(ordered) == 1:
        return ordered[0][0]
    top_count = ordered[0][1]
    tied = [action for action, count in ordered if count == top_count]
    if len(tied) == 1:
        return tied[0]
    return "mixed"


def _render_batch_summary_table(batches: list[WalletFlowBackfillBatchSummary]) -> list[str]:
    if not batches:
        return ["(none)"]
    lines = [
        "| batch_id | batch_rank_start | batch_rank_end | market_count | active_market_count | total_priority_score | action |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for batch in batches:
        lines.append(
            f"| {batch.batch_id} | {batch.batch_rank_start} | {batch.batch_rank_end} | "
            f"{batch.market_count} | {batch.active_market_count} | "
            f"{batch.total_priority_score:.4f} | {batch.action} |"
        )
    return lines


def _render_batch_rows_table(rows: list[WalletFlowBackfillPriority], batch_size: int) -> list[str]:
    if not rows:
        return ["(none)"]
    lines = [
        "| batch_id | rank | asset | market_slug | wallet_flow_rows | market_flow_hourly_rows | whale_flow_hourly_rows | priority_score | reasons | action |",
        "|---:|---:|---|---|---:|---:|---:|---:|---|---|",
    ]
    for idx, row in enumerate(rows):
        batch_id = (idx // batch_size) + 1
        lines.append(
            f"| {batch_id} | {row.rank} | {row.asset} | {row.market_slug} | "
            f"{row.wallet_flow_rows} | {row.market_flow_hourly_rows} | "
            f"{row.whale_flow_hourly_rows} | {row.priority_score:.4f} | "
            f"{'; '.join(row.reasons)} | {row.action} |"
        )
    return lines


def _rows_for_batch(
    all_rows: list[WalletFlowBackfillPriority],
    batch: WalletFlowBackfillBatchSummary,
    batch_size: int,
) -> list[WalletFlowBackfillPriority]:
    start_idx = (batch.batch_id - 1) * batch_size
    end_idx = start_idx + batch_size
    return all_rows[start_idx:end_idx]


def _write_batches_csv(path: Path, rows: list[WalletFlowBackfillPriority], *, batch_size: int) -> None:
    fieldnames = [
        "batch_id",
        "rank",
        "market_id",
        "market_slug",
        "asset",
        "is_active",
        "wallet_flow_rows",
        "market_flow_hourly_rows",
        "whale_flow_hourly_rows",
        "priority_score",
        "reasons",
        "action",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows):
            writer.writerow(
                {
                    "batch_id": (idx // max(1, batch_size)) + 1,
                    "rank": row.rank,
                    "market_id": row.market_id,
                    "market_slug": row.market_slug,
                    "asset": row.asset,
                    "is_active": row.is_active,
                    "wallet_flow_rows": row.wallet_flow_rows,
                    "market_flow_hourly_rows": row.market_flow_hourly_rows,
                    "whale_flow_hourly_rows": row.whale_flow_hourly_rows,
                    "priority_score": f"{row.priority_score:.4f}",
                    "reasons": ";".join(row.reasons),
                    "action": row.action,
                }
            )

