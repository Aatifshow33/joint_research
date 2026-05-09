"""Deterministic SignalCourt dashboard data model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
)
from joint_research.signalcourt.risk_gate import RiskConfig, default_tiny_account_risk_config
from joint_research.signalcourt.snapshot import SignalCourtPipelineSnapshot, build_pipeline_snapshot

LANE_TITLES = {
    "wallet_flow_signal": "Wallet-Flow",
    "derivatives_regime": "Derivatives-Regime",
}


@dataclass(frozen=True)
class SignalCourtDashboardLane:
    lane: str
    signal_id: str
    title: str
    final_status: str
    blocked: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    verdict: str
    trade_action: str
    paper_action: str
    risk_allowed: bool
    account_equity_usd: float
    max_risk_usd: float
    top_blockers: list[str]
    block_reasons: list[str]
    next_required_evidence: list[str]
    operator_summary: str
    source_artifacts: list[str]


@dataclass(frozen=True)
class SignalCourtDashboardModel:
    title: str
    product_mode: str
    lanes: list[SignalCourtDashboardLane]
    global_status: str
    any_order_allowed: bool
    paper_orders_allowed_count: int
    live_orders_allowed_count: int
    blocked_lanes_count: int
    warnings: list[str]
    next_best_action: str
    non_authorization_notice: str


def build_dashboard_model(
    snapshots: list[SignalCourtPipelineSnapshot],
) -> SignalCourtDashboardModel:
    lanes = [_snapshot_to_lane(snapshot) for snapshot in snapshots]
    paper_orders_allowed_count = sum(1 for lane in lanes if lane.paper_order_allowed)
    live_orders_allowed_count = sum(1 for lane in lanes if lane.live_order_allowed)
    blocked_lanes_count = sum(1 for lane in lanes if lane.blocked)
    any_order_allowed = paper_orders_allowed_count > 0 or live_orders_allowed_count > 0

    warnings: list[str] = []
    if blocked_lanes_count > 0:
        warnings.append("Blocked lanes present; execution remains disabled.")
    if paper_orders_allowed_count == 0:
        warnings.append("No paper orders are currently allowed.")
    if live_orders_allowed_count == 0:
        warnings.append("No live trading is allowed in this phase.")
    if any(
        "RESEARCH_ONLY" in snapshot.readiness_status
        or "EXPLORATORY_ONLY" in snapshot.readiness_status
        for snapshot in snapshots
    ):
        warnings.append("Research-only posture remains active.")

    global_status = "BLOCKED_RESEARCH_ONLY_NO_EXECUTION"
    next_best_action = (
        "Strengthen diagnostics and paper-validation evidence before any execution review."
    )

    non_auth_candidates = [snapshot.non_authorization_notice for snapshot in snapshots if snapshot.non_authorization_notice]
    non_authorization_notice = (
        non_auth_candidates[0]
        if non_auth_candidates
        else "Research-only model; no trade execution is authorized."
    )

    return SignalCourtDashboardModel(
        title="SignalCourt Trader Dashboard Model",
        product_mode="RESEARCH_ONLY",
        lanes=lanes,
        global_status=global_status,
        any_order_allowed=any_order_allowed,
        paper_orders_allowed_count=paper_orders_allowed_count,
        live_orders_allowed_count=live_orders_allowed_count,
        blocked_lanes_count=blocked_lanes_count,
        warnings=warnings,
        next_best_action=next_best_action,
        non_authorization_notice=non_authorization_notice,
    )


def build_current_signalcourt_dashboard_model(
    *,
    wallet_signal_summary_md_path: Path,
    wallet_rejection_diagnostics_csv_path: Path,
    wallet_rejection_summary_md_path: Path,
    derivatives_results_csv_path: Path,
    derivatives_candidates_json_path: Path,
    derivatives_summary_md_path: Path,
    wallet_risk_config: RiskConfig | None = None,
    derivatives_risk_config: RiskConfig | None = None,
) -> SignalCourtDashboardModel:
    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=wallet_signal_summary_md_path,
        rejection_diagnostics_csv_path=wallet_rejection_diagnostics_csv_path,
        rejection_summary_md_path=wallet_rejection_summary_md_path,
        risk_config=wallet_risk_config or default_tiny_account_risk_config(50.0),
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=derivatives_results_csv_path,
        candidates_json_path=derivatives_candidates_json_path,
        summary_md_path=derivatives_summary_md_path,
        risk_config=derivatives_risk_config or default_tiny_account_risk_config(100.0),
    )
    snapshots = [
        build_pipeline_snapshot(wallet_pipeline),
        build_pipeline_snapshot(derivatives_pipeline),
    ]
    return build_dashboard_model(snapshots)


def _snapshot_to_lane(snapshot: SignalCourtPipelineSnapshot) -> SignalCourtDashboardLane:
    return SignalCourtDashboardLane(
        lane=snapshot.lane,
        signal_id=snapshot.signal_id,
        title=LANE_TITLES.get(snapshot.lane, snapshot.lane.replace("_", " ").title()),
        final_status=snapshot.final_status,
        blocked=snapshot.blocked,
        paper_order_allowed=snapshot.paper_order_allowed,
        live_order_allowed=snapshot.live_order_allowed,
        verdict=snapshot.verdict,
        trade_action=snapshot.trade_action,
        paper_action=snapshot.paper_action,
        risk_allowed=snapshot.risk_allowed,
        account_equity_usd=snapshot.account_equity_usd,
        max_risk_usd=snapshot.max_risk_usd,
        top_blockers=list(snapshot.top_blockers),
        block_reasons=list(snapshot.block_reasons),
        next_required_evidence=list(snapshot.next_required_evidence),
        operator_summary=snapshot.operator_summary,
        source_artifacts=list(snapshot.source_artifacts),
    )
