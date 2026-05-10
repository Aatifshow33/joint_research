"""Deterministic in-memory renderer for SignalCourt dashboard summaries."""

from __future__ import annotations

from pathlib import Path

from joint_research.signalcourt.dashboard_model import (
    SignalCourtDashboardLane,
    SignalCourtDashboardModel,
    build_current_signalcourt_dashboard_model,
)
from joint_research.signalcourt.risk_gate import RiskConfig


def render_dashboard_summary(model: SignalCourtDashboardModel) -> str:
    lines: list[str] = [
        "# SignalCourt Trader Dashboard Summary",
        f"- Title: {model.title}",
        f"- Product Mode: {model.product_mode}",
        f"- Global Status: {model.global_status}",
        f"- Any Order Allowed: {_format_bool(model.any_order_allowed)}",
        f"- Paper Orders Allowed Count: {model.paper_orders_allowed_count}",
        f"- Live Orders Allowed Count: {model.live_orders_allowed_count}",
        f"- Blocked Lanes Count: {model.blocked_lanes_count}",
        "- Execution Safety: No executable paper orders and no live trading in current phase.",
    ]

    lines.append("")
    lines.append("## Warnings")
    if model.warnings:
        lines.extend(f"- {warning}" for warning in model.warnings)
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Next Best Action",
            model.next_best_action,
            "",
            "## Lane Summaries",
        ]
    )
    lines.extend(_render_lane(lane) for lane in model.lanes)
    lines.extend(
        [
            "",
            "## Non-Authorization Notice",
            model.non_authorization_notice,
        ]
    )
    return "\n".join(lines)


def render_current_signalcourt_dashboard_summary(
    *,
    wallet_signal_summary_md_path: Path,
    wallet_rejection_diagnostics_csv_path: Path,
    wallet_rejection_summary_md_path: Path,
    derivatives_results_csv_path: Path,
    derivatives_candidates_json_path: Path,
    derivatives_summary_md_path: Path,
    wallet_risk_config: RiskConfig | None = None,
    derivatives_risk_config: RiskConfig | None = None,
) -> str:
    model = build_current_signalcourt_dashboard_model(
        wallet_signal_summary_md_path=wallet_signal_summary_md_path,
        wallet_rejection_diagnostics_csv_path=wallet_rejection_diagnostics_csv_path,
        wallet_rejection_summary_md_path=wallet_rejection_summary_md_path,
        derivatives_results_csv_path=derivatives_results_csv_path,
        derivatives_candidates_json_path=derivatives_candidates_json_path,
        derivatives_summary_md_path=derivatives_summary_md_path,
        wallet_risk_config=wallet_risk_config,
        derivatives_risk_config=derivatives_risk_config,
    )
    return render_dashboard_summary(model)


def _render_lane(lane: SignalCourtDashboardLane) -> str:
    top_blockers = ", ".join(lane.top_blockers) if lane.top_blockers else "None"
    block_reasons = ", ".join(lane.block_reasons) if lane.block_reasons else "None"
    next_required_evidence = (
        ", ".join(lane.next_required_evidence) if lane.next_required_evidence else "None"
    )
    source_artifacts = ", ".join(lane.source_artifacts) if lane.source_artifacts else "None"
    return "\n".join(
        [
            "",
            f"### {lane.title} ({lane.lane})",
            f"- Signal ID: {lane.signal_id}",
            f"- Final Status: {lane.final_status}",
            f"- Blocked: {_format_bool(lane.blocked)}",
            f"- Verdict: {lane.verdict}",
            f"- Trade Action: {lane.trade_action}",
            f"- Paper Action: {lane.paper_action}",
            f"- Risk Allowed: {_format_bool(lane.risk_allowed)}",
            f"- Paper Order Allowed: {_format_bool(lane.paper_order_allowed)}",
            f"- Live Order Allowed: {_format_bool(lane.live_order_allowed)}",
            f"- Max Risk USD: {lane.max_risk_usd:.2f}",
            f"- Account Equity USD: {lane.account_equity_usd:.2f}",
            f"- Top Blockers: {top_blockers}",
            f"- Block Reasons: {block_reasons}",
            f"- Next Required Evidence: {next_required_evidence}",
            f"- Source Artifacts: {source_artifacts}",
            f"- Operator Summary: {lane.operator_summary}",
        ]
    )


def _format_bool(value: bool) -> str:
    return "true" if value else "false"
