"""Deterministic compact snapshot model for SignalCourt pipeline review."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.pipeline import SignalCourtPipelineResult


@dataclass(frozen=True)
class SignalCourtPipelineSnapshot:
    lane: str
    signal_id: str
    final_status: str
    blocked: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    readiness_status: str
    passport_status: str
    verdict: str
    trade_action: str
    paper_action: str
    risk_allowed: bool
    top_blockers: list[str]
    block_reasons: list[str]
    account_equity_usd: float
    max_risk_usd: float
    max_position_notional_usd: float
    source_artifacts: list[str]
    next_required_evidence: list[str]
    operator_summary: str
    non_authorization_notice: str


def build_pipeline_snapshot(
    pipeline_result: SignalCourtPipelineResult,
) -> SignalCourtPipelineSnapshot:
    top_blockers = list(pipeline_result.readiness.top_blockers)
    block_reasons = list(dict.fromkeys(pipeline_result.journal_entry.block_reasons))

    operator_summary = (
        f"Lane {pipeline_result.lane} is blocked and not tradeable. "
        f"Final status={pipeline_result.final_status}. "
        f"Research-only status={pipeline_result.readiness.status}."
    )

    return SignalCourtPipelineSnapshot(
        lane=pipeline_result.lane,
        signal_id=pipeline_result.signal_id,
        final_status=pipeline_result.final_status,
        blocked=pipeline_result.blocked,
        paper_order_allowed=pipeline_result.paper_order_allowed,
        live_order_allowed=pipeline_result.live_order_allowed,
        readiness_status=pipeline_result.readiness.status,
        passport_status=pipeline_result.passport.status,
        verdict=pipeline_result.verdict.verdict,
        trade_action=pipeline_result.trade_decision.action,
        paper_action=pipeline_result.paper_decision.paper_action,
        risk_allowed=pipeline_result.risk_gate.risk_allowed,
        top_blockers=top_blockers,
        block_reasons=block_reasons,
        account_equity_usd=pipeline_result.risk_gate.account_equity_usd,
        max_risk_usd=pipeline_result.risk_gate.max_risk_usd,
        max_position_notional_usd=pipeline_result.risk_gate.max_position_notional_usd,
        source_artifacts=list(pipeline_result.readiness.source_artifacts),
        next_required_evidence=list(pipeline_result.readiness.next_required_evidence),
        operator_summary=operator_summary,
        non_authorization_notice=pipeline_result.non_authorization_notice,
    )


def snapshot_allows_order(snapshot: SignalCourtPipelineSnapshot) -> bool:
    if snapshot.blocked:
        return False
    if not snapshot.paper_order_allowed:
        return False
    # Live order permission is reserved for a future live phase and should not pass here.
    if snapshot.live_order_allowed:
        return False
    return True
