
"""Wallet-flow diagnostic promotion planning helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from joint_research.research.wallet_flow_diagnostic_triage import (
    build_wallet_flow_diagnostic_triage,
)
from joint_research.research.wallet_flow_signal import (
    WalletFlowNearMiss,
    WalletFlowRejectionDiagnostic,
    rank_wallet_flow_near_misses,
)

PROMOTION_PLAN_FILENAME = "wallet_flow_promotion_plan.md"


@dataclass(frozen=True)
class WalletFlowPromotionPlan:
    total_diagnostics: int
    total_rejected: int
    retained_non_promoted: int
    action_counts: list[tuple[str, int]]
    blocker_counts: list[tuple[str, int]]
    data_gap_counts: list[tuple[str, int]]
    near_misses: list[WalletFlowNearMiss]


def build_wallet_flow_promotion_plan(
    diagnostics: list[WalletFlowRejectionDiagnostic],
    *,
    near_miss_limit: int = 10,
) -> WalletFlowPromotionPlan:
    triage = build_wallet_flow_diagnostic_triage(
        diagnostics,
        near_miss_limit=near_miss_limit,
    )
    action_counter: Counter[str] = Counter()
    blocker_counter: Counter[str] = Counter()
    data_gap_counter: Counter[str] = Counter()

    for diagnostic in diagnostics:
        reasons = _split_reasons(diagnostic.rejection_reasons)
        action_counter.update(_promotion_actions_for(diagnostic, reasons))
        blocker_counter.update(_blockers_for(diagnostic, reasons))
        data_gap_counter.update(_data_gaps_for(reasons))

    return WalletFlowPromotionPlan(
        total_diagnostics=triage.total_diagnostics,
        total_rejected=triage.total_rejected,
        retained_non_promoted=triage.retained_non_promoted,
        action_counts=_ordered_counts(action_counter),
        blocker_counts=_ordered_counts(blocker_counter),
        data_gap_counts=_ordered_counts(data_gap_counter),
        near_misses=rank_wallet_flow_near_misses(diagnostics, limit=near_miss_limit),
    )


def write_wallet_flow_promotion_plan_report(
    *,
    output_dir: Path,
    diagnostics: list[WalletFlowRejectionDiagnostic],
    near_miss_limit: int = 10,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = build_wallet_flow_promotion_plan(
        diagnostics,
        near_miss_limit=near_miss_limit,
    )
    report_path = output_dir / PROMOTION_PLAN_FILENAME
    report_path.write_text(render_wallet_flow_promotion_plan(plan))
    return report_path


def render_wallet_flow_promotion_plan(plan: WalletFlowPromotionPlan) -> str:
    lines = [
        "# Wallet Flow Promotion Plan",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "",
        "No thresholds changed.",
        "No candidates approved.",
        "This is a data/action plan only.",
        "",
        "## Summary",
        "",
        f"- diagnostics: {plan.total_diagnostics}",
        f"- rejected_candidates: {plan.total_rejected}",
        f"- retained_non_promoted: {plan.retained_non_promoted}",
        "",
        "## Required Next Actions",
        "",
    ]
    lines.extend(_render_count_table("action", plan.action_counts))
    lines.extend(["", "## Current Promotion Blockers", ""])
    lines.extend(_render_count_table("blocker", plan.blocker_counts))
    lines.extend(["", "## Data Gaps To Backfill", ""])
    lines.extend(_render_count_table("data_gap", plan.data_gap_counts))
    lines.extend(["", "## Near Misses To Recheck After Data Backfill", ""])
    lines.extend(_render_near_miss_table(plan.near_misses))
    lines.extend(
        [
            "",
            "## Promotion Rule",
            "",
            "No wallet-flow candidate should be promoted from this report alone.",
            "A future promotion requires fresh diagnostics, unchanged thresholds, and separate simulation validation.",
        ]
    )
    return "\\n".join(lines).rstrip() + "\\n"


def _promotion_actions_for(
    diagnostic: WalletFlowRejectionDiagnostic,
    reasons: list[str],
) -> set[str]:
    reason_set = set(reasons)
    actions: set[str] = set()

    if reason_set & {
        "low_sample_count",
        "insufficient_samples",
        "insufficient_unique_flow_hours",
    }:
        actions.add("backfill more wallet-flow history")

    if reason_set & {
        "insufficient_active_wallet_coverage",
        "insufficient_non_zero_net_flow_coverage",
        "thin_copy_flow_warning",
        "copy_flow_too_thin",
    }:
        actions.add("improve active wallet and non-zero flow coverage")

    if reason_set & {
        "no_train_edge",
        "train_test_direction_mismatch",
        "weak_win_rate",
        "weak_stability",
        "unstable_train_test_warning",
    }:
        actions.add("wait for stronger forward-return confirmation")

    if reason_set & {
        "no_net_improvement_after_cost",
        "improvement_below_cost_buffer",
        "weak_test_improvement",
        "net_improvement_below_cost",
    }:
        actions.add("keep rejected until net edge clears costs")

    if "duplicate_segment_competition" in reason_set:
        actions.add("inspect stronger duplicate segment before promotion")

    if (
        diagnostic.retained_after_dedup
        and diagnostic.final_grade.upper() in {"WEAK", "WATCHLIST"}
    ):
        actions.add("rerun after backfill because candidate was retained but not promoted")

    if not actions:
        actions.add("manual review required before any future promotion")

    return actions


def _blockers_for(
    diagnostic: WalletFlowRejectionDiagnostic,
    reasons: list[str],
) -> set[str]:
    reason_set = set(reasons)
    blockers: set[str] = set()

    if diagnostic.final_grade.upper() == "REJECTED":
        blockers.add("final grade rejected")
    if diagnostic.final_grade.upper() in {"WEAK", "WATCHLIST"}:
        blockers.add("final grade below simulation ready")
    if reason_set & {
        "no_net_improvement_after_cost",
        "improvement_below_cost_buffer",
        "weak_test_improvement",
        "net_improvement_below_cost",
    }:
        blockers.add("net edge below cost-aware requirement")
    if reason_set & {
        "no_train_edge",
        "train_test_direction_mismatch",
        "weak_win_rate",
        "weak_stability",
        "unstable_train_test_warning",
    }:
        blockers.add("forward-return evidence not stable enough")
    if reason_set & {
        "low_sample_count",
        "insufficient_samples",
        "insufficient_unique_flow_hours",
        "insufficient_active_wallet_coverage",
        "insufficient_non_zero_net_flow_coverage",
        "thin_copy_flow_warning",
        "copy_flow_too_thin",
    }:
        blockers.add("coverage too thin")
    if "duplicate_segment_competition" in reason_set:
        blockers.add("duplicate segment competition")
    if not blockers:
        blockers.add("uncategorized blocker")

    return blockers


def _data_gaps_for(reasons: list[str]) -> set[str]:
    reason_set = set(reasons)
    gaps: set[str] = set()

    if reason_set & {"low_sample_count", "insufficient_samples"}:
        gaps.add("more total segment samples")
    if "insufficient_unique_flow_hours" in reason_set:
        gaps.add("more unique wallet-flow hours")
    if "insufficient_active_wallet_coverage" in reason_set:
        gaps.add("more active wallet coverage")
    if "insufficient_non_zero_net_flow_coverage" in reason_set:
        gaps.add("more non-zero net-flow coverage")
    if reason_set & {"thin_copy_flow_warning", "copy_flow_too_thin"}:
        gaps.add("more copy-flow observations")
    if not gaps:
        gaps.add("no direct data gap identified")

    return gaps


def _render_count_table(label: str, rows: list[tuple[str, int]]) -> list[str]:
    if not rows:
        return ["(none)"]
    lines = [f"| {label} | count |", "|---|---:|"]
    lines.extend(f"| {name} | {count} |" for name, count in rows)
    return lines


def _render_near_miss_table(near_misses: list[WalletFlowNearMiss]) -> list[str]:
    if not near_misses:
        return ["(none)"]
    lines = [
        "| rank | candidate_rank | grade | candidate_key | reasons | improvement | net_after_cost |",
        "|---:|---:|---|---|---|---:|---:|",
    ]
    for item in near_misses:
        lines.append(
            "| "
            f"{item.rank} | {item.candidate_rank} | {item.final_grade} | "
            f"{item.candidate_key} | {item.reasons} | "
            f"{item.improvement:.6f} | {item.net_after_cost:.6f} |"
        )
    return lines


def _split_reasons(value: str) -> list[str]:
    return sorted({reason for reason in value.split(";") if reason})


def _ordered_counts(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))
