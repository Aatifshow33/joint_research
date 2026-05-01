"""Wallet-flow backfill priority planner helpers."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from joint_research.research.wallet_flow_coverage_gate import (
    WalletFlowCoverageRow,
    read_wallet_flow_coverage_rows,
)

BACKFILL_PRIORITY_MD_FILENAME = "wallet_flow_backfill_priority.md"
BACKFILL_PRIORITY_CSV_FILENAME = "wallet_flow_backfill_priority.csv"


@dataclass(frozen=True)
class WalletFlowBackfillPriorityThresholds:
    min_wallet_flow_rows: int = 24
    min_market_flow_hourly_rows: int = 24
    min_whale_flow_hourly_rows: int = 24


@dataclass(frozen=True)
class WalletFlowBackfillPriority:
    rank: int
    market_id: str
    market_slug: str
    asset: str
    is_active: bool
    is_closed: bool
    volume_1mo_usd: float
    volume_total_usd: float
    wallet_flow_rows: int
    trade_rows: int
    copy_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int
    priority_score: float
    reasons: tuple[str, ...]
    action: str


@dataclass(frozen=True)
class WalletFlowBackfillPriorityPlan:
    coverage_csv: Path
    total_markets: int
    covered_markets: int
    backfill_markets: int
    active_backfill_markets: int
    reason_counts: list[tuple[str, int]]
    priorities: list[WalletFlowBackfillPriority]


def run_wallet_flow_backfill_priority_plan(
    *,
    coverage_csv: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    top_limit: int = 25,
) -> WalletFlowBackfillPriorityPlan:
    rows = read_wallet_flow_coverage_rows(coverage_csv)
    return build_wallet_flow_backfill_priority_plan(
        coverage_csv=coverage_csv,
        rows=rows,
        thresholds=thresholds,
        top_limit=top_limit,
    )


def build_wallet_flow_backfill_priority_plan(
    *,
    coverage_csv: Path,
    rows: list[WalletFlowCoverageRow],
    thresholds: WalletFlowBackfillPriorityThresholds,
    top_limit: int = 25,
) -> WalletFlowBackfillPriorityPlan:
    scored: list[tuple[float, WalletFlowCoverageRow, tuple[str, ...], str]] = []
    reason_counter: Counter[str] = Counter()

    for row in rows:
        score, reasons, action = _priority_for_row(row, thresholds)
        if not reasons:
            continue
        reason_counter.update(reasons)
        scored.append((score, row, reasons, action))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].asset,
            item[1].market_slug,
            item[1].market_id,
        )
    )

    priorities = [
        WalletFlowBackfillPriority(
            rank=index,
            market_id=row.market_id,
            market_slug=row.market_slug,
            asset=row.asset,
            is_active=row.is_active,
            is_closed=row.is_closed,
            volume_1mo_usd=row.volume_1mo_usd,
            volume_total_usd=row.volume_total_usd,
            wallet_flow_rows=row.wallet_flow_rows,
            trade_rows=row.trade_rows,
            copy_rows=row.copy_rows,
            market_flow_hourly_rows=row.market_flow_hourly_rows,
            whale_flow_hourly_rows=row.whale_flow_hourly_rows,
            priority_score=score,
            reasons=reasons,
            action=action,
        )
        for index, (score, row, reasons, action) in enumerate(scored[:top_limit], start=1)
    ]

    return WalletFlowBackfillPriorityPlan(
        coverage_csv=coverage_csv,
        total_markets=len(rows),
        covered_markets=sum(1 for row in rows if row.wallet_flow_rows > 0),
        backfill_markets=len(scored),
        active_backfill_markets=sum(1 for _, row, _, _ in scored if row.is_active),
        reason_counts=sorted(reason_counter.items(), key=lambda item: (-item[1], item[0])),
        priorities=priorities,
    )


def write_wallet_flow_backfill_priority_artifacts(
    *,
    coverage_csv: Path,
    output_dir: Path,
    thresholds: WalletFlowBackfillPriorityThresholds,
    top_limit: int = 25,
) -> tuple[Path, Path, WalletFlowBackfillPriorityPlan]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = run_wallet_flow_backfill_priority_plan(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        top_limit=top_limit,
    )
    report_path = output_dir / BACKFILL_PRIORITY_MD_FILENAME
    csv_path = output_dir / BACKFILL_PRIORITY_CSV_FILENAME
    report_path.write_text(render_wallet_flow_backfill_priority_report(plan, thresholds))
    _write_priority_csv(csv_path, plan.priorities)
    return report_path, csv_path, plan


def render_wallet_flow_backfill_priority_report(
    plan: WalletFlowBackfillPriorityPlan,
    thresholds: WalletFlowBackfillPriorityThresholds,
) -> str:
    lines = [
        "# Wallet Flow Backfill Priority Plan",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "",
        "## Summary",
        "",
        f"- coverage_csv: {plan.coverage_csv}",
        f"- total_markets: {plan.total_markets}",
        f"- covered_markets: {plan.covered_markets}",
        f"- backfill_markets: {plan.backfill_markets}",
        f"- active_backfill_markets: {plan.active_backfill_markets}",
        "",
        "## Thresholds",
        "",
        f"- min_wallet_flow_rows: {thresholds.min_wallet_flow_rows}",
        f"- min_market_flow_hourly_rows: {thresholds.min_market_flow_hourly_rows}",
        f"- min_whale_flow_hourly_rows: {thresholds.min_whale_flow_hourly_rows}",
        "",
        "## Reason Counts",
        "",
    ]
    if plan.reason_counts:
        lines.extend(f"- {reason}: {count}" for reason, count in plan.reason_counts)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Priority Queue",
            "",
        ]
    )
    lines.extend(_render_priority_table(plan.priorities))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report ranks data backfill needs only.",
            "It does not approve wallet-flow candidates or modify promotion thresholds.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _priority_for_row(
    row: WalletFlowCoverageRow,
    thresholds: WalletFlowBackfillPriorityThresholds,
) -> tuple[float, tuple[str, ...], str]:
    reasons: list[str] = []
    score = 0.0

    wallet_deficit = max(thresholds.min_wallet_flow_rows - row.wallet_flow_rows, 0)
    market_hourly_deficit = max(
        thresholds.min_market_flow_hourly_rows - row.market_flow_hourly_rows,
        0,
    )
    whale_hourly_deficit = max(
        thresholds.min_whale_flow_hourly_rows - row.whale_flow_hourly_rows,
        0,
    )

    if wallet_deficit:
        reasons.append("wallet-flow rows below target")
        score += wallet_deficit * 100
    if market_hourly_deficit:
        reasons.append("market-flow hourly rows below target")
        score += market_hourly_deficit * 40
    if whale_hourly_deficit:
        reasons.append("whale-flow hourly rows below target")
        score += whale_hourly_deficit * 40

    if not reasons:
        return 0.0, (), "no backfill needed"

    if row.is_active:
        score += 25
    score += min(row.volume_1mo_usd / 100_000, 25)
    score += min(row.volume_total_usd / 1_000_000, 25)

    if "wallet-flow rows below target" in reasons:
        action = "backfill wallet trades and hourly aggregates"
    elif "market-flow hourly rows below target" in reasons:
        action = "backfill market-flow hourly aggregates"
    else:
        action = "backfill whale-flow hourly aggregates"

    return score, tuple(reasons), action


def _render_priority_table(priorities: list[WalletFlowBackfillPriority]) -> list[str]:
    if not priorities:
        return ["(none)"]
    lines = [
        "| rank | asset | market_slug | wallet_flow_rows | market_flow_hourly_rows | whale_flow_hourly_rows | priority_score | reasons | action |",
        "|---:|---|---|---:|---:|---:|---:|---|---|",
    ]
    for priority in priorities:
        lines.append(
            f"| {priority.rank} | {priority.asset} | {priority.market_slug} | "
            f"{priority.wallet_flow_rows} | {priority.market_flow_hourly_rows} | "
            f"{priority.whale_flow_hourly_rows} | {priority.priority_score:.4f} | "
            f"{'; '.join(priority.reasons)} | {priority.action} |"
        )
    return lines


def _write_priority_csv(path: Path, priorities: list[WalletFlowBackfillPriority]) -> None:
    fieldnames = [
        "rank",
        "market_id",
        "market_slug",
        "asset",
        "is_active",
        "is_closed",
        "volume_1mo_usd",
        "volume_total_usd",
        "wallet_flow_rows",
        "trade_rows",
        "copy_rows",
        "market_flow_hourly_rows",
        "whale_flow_hourly_rows",
        "priority_score",
        "reasons",
        "action",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for priority in priorities:
            writer.writerow(
                {
                    "rank": priority.rank,
                    "market_id": priority.market_id,
                    "market_slug": priority.market_slug,
                    "asset": priority.asset,
                    "is_active": priority.is_active,
                    "is_closed": priority.is_closed,
                    "volume_1mo_usd": priority.volume_1mo_usd,
                    "volume_total_usd": priority.volume_total_usd,
                    "wallet_flow_rows": priority.wallet_flow_rows,
                    "trade_rows": priority.trade_rows,
                    "copy_rows": priority.copy_rows,
                    "market_flow_hourly_rows": priority.market_flow_hourly_rows,
                    "whale_flow_hourly_rows": priority.whale_flow_hourly_rows,
                    "priority_score": f"{priority.priority_score:.4f}",
                    "reasons": ";".join(priority.reasons),
                    "action": priority.action,
                }
            )
