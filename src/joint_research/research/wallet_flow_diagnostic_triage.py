"""Wallet-flow rejection diagnostic triage report helpers."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from joint_research.research.wallet_flow_signal import (
    WalletFlowNearMiss,
    WalletFlowRejectionDiagnostic,
    rank_wallet_flow_near_misses,
)

TRIAGE_REPORT_FILENAME = "wallet_flow_diagnostic_triage.md"
NON_PROMOTED_GRADES = {"REJECTED", "WEAK", "WATCHLIST"}
PROMOTED_GRADES = {"SIMULATION_READY"}


@dataclass(frozen=True)
class WalletFlowDiagnosticTriage:
    total_diagnostics: int
    total_rejected: int
    retained_non_promoted: int
    duplicate_segment_competition_count: int
    reason_counts: list[tuple[str, int]]
    action_bucket_counts: list[tuple[str, int]]
    horizon_counts: list[tuple[int, int]]
    segment_counts: list[tuple[str, int]]
    near_misses: list[WalletFlowNearMiss]


def read_wallet_flow_rejection_diagnostics(path: Path) -> list[WalletFlowRejectionDiagnostic]:
    """Read rejection diagnostics CSV, returning an empty list when missing."""

    if not path.exists():
        return []

    rows: list[WalletFlowRejectionDiagnostic] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                WalletFlowRejectionDiagnostic(
                    rank=_int_value(row.get("rank")),
                    asset=row.get("asset", ""),
                    market_id=row.get("market_id", ""),
                    market_slug=_optional_text(row.get("market_slug")),
                    token_id=row.get("token_id", ""),
                    horizon_hours=_int_value(row.get("horizon_hours")),
                    feature_name=row.get("feature_name", ""),
                    segment_type=row.get("segment_type", ""),
                    segment_value=row.get("segment_value", ""),
                    final_grade=row.get("final_grade", ""),
                    retained_after_dedup=_bool_value(row.get("retained_after_dedup")),
                    rejection_reasons=row.get("rejection_reasons", ""),
                    sample_count=_int_value(row.get("sample_count")),
                    test_samples=_int_value(row.get("test_samples")),
                    unique_flow_hours=_int_value(row.get("unique_flow_hours")),
                    active_wallet_coverage=_float_value(row.get("active_wallet_coverage")),
                    non_zero_net_flow_coverage=_float_value(row.get("non_zero_net_flow_coverage")),
                    test_improvement_over_baseline=_float_value(
                        row.get("test_improvement_over_baseline")
                    ),
                    net_test_improvement_after_cost=_float_value(
                        row.get("net_test_improvement_after_cost")
                    ),
                    test_win_rate=_float_value(row.get("test_win_rate")),
                    stability=_float_value(row.get("stability")),
                )
            )
    return rows


def build_wallet_flow_diagnostic_triage(
    diagnostics: list[WalletFlowRejectionDiagnostic],
    *,
    near_miss_limit: int = 10,
) -> WalletFlowDiagnosticTriage:
    reason_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    horizon_counter: Counter[int] = Counter()
    segment_counter: Counter[str] = Counter()

    total_rejected = 0
    retained_non_promoted = 0
    duplicate_segment_competition_count = 0

    for diagnostic in diagnostics:
        grade = diagnostic.final_grade.upper()
        if grade == "REJECTED":
            total_rejected += 1
        if diagnostic.retained_after_dedup and grade in NON_PROMOTED_GRADES:
            retained_non_promoted += 1

        reasons = _split_reasons(diagnostic.rejection_reasons)
        reason_counter.update(reasons)
        if "duplicate_segment_competition" in reasons:
            duplicate_segment_competition_count += 1

        action_buckets = _action_buckets_for(diagnostic, reasons)
        action_counter.update(sorted(action_buckets))
        horizon_counter[diagnostic.horizon_hours] += 1
        segment_counter[f"{diagnostic.segment_type}:{diagnostic.segment_value}"] += 1

    return WalletFlowDiagnosticTriage(
        total_diagnostics=len(diagnostics),
        total_rejected=total_rejected,
        retained_non_promoted=retained_non_promoted,
        duplicate_segment_competition_count=duplicate_segment_competition_count,
        reason_counts=_ordered_str_counts(reason_counter),
        action_bucket_counts=_ordered_str_counts(action_counter),
        horizon_counts=sorted(horizon_counter.items()),
        segment_counts=_ordered_str_counts(segment_counter),
        near_misses=rank_wallet_flow_near_misses(diagnostics, limit=near_miss_limit),
    )


def write_wallet_flow_diagnostic_triage_report(
    *,
    output_dir: Path,
    diagnostics: list[WalletFlowRejectionDiagnostic],
    near_miss_limit: int = 10,
) -> Path:
    """Write deterministic wallet-flow triage markdown and return the path."""

    output_dir.mkdir(parents=True, exist_ok=True)
    triage = build_wallet_flow_diagnostic_triage(
        diagnostics,
        near_miss_limit=near_miss_limit,
    )
    report_path = output_dir / TRIAGE_REPORT_FILENAME
    report_path.write_text(render_wallet_flow_diagnostic_triage(triage))
    return report_path


def render_wallet_flow_diagnostic_triage(triage: WalletFlowDiagnosticTriage) -> str:
    lines = [
        "# Wallet Flow Diagnostic Triage",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "",
        "No promotion thresholds were changed.",
        "This report explains rejection causes; it does not approve candidates.",
        "",
        "## Summary",
        "",
        f"- diagnostics: {triage.total_diagnostics}",
        f"- rejected_candidates: {triage.total_rejected}",
        f"- retained_non_promoted: {triage.retained_non_promoted}",
        f"- duplicate_segment_competition: {triage.duplicate_segment_competition_count}",
        "",
        "## Suggested Next Action Buckets",
        "",
    ]
    lines.extend(_render_count_table("action", triage.action_bucket_counts))
    lines.extend(["", "## Rejection Reason Counts", ""])
    lines.extend(_render_count_table("reason", triage.reason_counts))
    lines.extend(["", "## Horizon Breakdown", ""])
    lines.extend(_render_horizon_table(triage.horizon_counts))
    lines.extend(["", "## Segment Breakdown", ""])
    lines.extend(_render_count_table("segment", triage.segment_counts))
    lines.extend(["", "## Top Near Misses", ""])
    lines.extend(_render_near_miss_table(triage.near_misses))
    return "\n".join(lines).rstrip() + "\n"


def _render_count_table(label: str, rows: list[tuple[str, int]]) -> list[str]:
    if not rows:
        return ["(none)"]
    lines = [f"| {label} | count |", "|---|---:|"]
    lines.extend(f"| {name} | {count} |" for name, count in rows)
    return lines


def _render_horizon_table(rows: list[tuple[int, int]]) -> list[str]:
    if not rows:
        return ["(none)"]
    lines = ["| horizon_hours | count |", "|---:|---:|"]
    lines.extend(f"| {horizon} | {count} |" for horizon, count in rows)
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


def _action_buckets_for(
    diagnostic: WalletFlowRejectionDiagnostic,
    reasons: list[str],
) -> set[str]:
    buckets: set[str] = set()
    reason_set = set(reasons)

    if reason_set & {
        "low_sample_count",
        "insufficient_samples",
        "insufficient_unique_flow_hours",
        "insufficient_active_wallet_coverage",
        "insufficient_non_zero_net_flow_coverage",
        "thin_copy_flow_warning",
        "copy_flow_too_thin",
    }:
        buckets.add("increase sample coverage")
    if "duplicate_segment_competition" in reason_set:
        buckets.add("inspect duplicate segment competition")
    if reason_set & {
        "no_train_edge",
        "train_test_direction_mismatch",
        "weak_win_rate",
        "weak_stability",
        "unstable_train_test_warning",
    }:
        buckets.add("insufficient forward return support")
    if reason_set & {
        "no_net_improvement_after_cost",
        "improvement_below_cost_buffer",
        "weak_test_improvement",
        "net_improvement_below_cost",
    }:
        buckets.add("threshold gap remains too large")
    if (
        diagnostic.retained_after_dedup
        and diagnostic.final_grade.upper() in {"WEAK", "WATCHLIST"}
    ):
        buckets.add("candidate retained but not promoted")
    if not buckets:
        buckets.add("review uncategorized rejection reason")
    return buckets


def _split_reasons(value: str) -> list[str]:
    return sorted({reason for reason in value.split(";") if reason})


def _ordered_str_counts(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _optional_text(value: str | None) -> str | None:
    if value in (None, "", "None"):
        return None
    return value


def _int_value(value: str | None) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _float_value(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _bool_value(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}
