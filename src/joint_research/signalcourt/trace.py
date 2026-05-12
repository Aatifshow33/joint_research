"""Deterministic in-memory SignalCourt trace schema for observability."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.pipeline import SignalCourtPipelineResult

TRACE_BLOCKED_STATUS = "BLOCKED"
TRACE_READY_STATUS = "READY"


@dataclass(frozen=True)
class SignalCourtTraceStep:
    step_name: str
    component: str
    status: str
    input_summary: str
    output_summary: str
    blockers: list[str]
    source_artifacts: list[str]
    non_authorization_notice: str


@dataclass(frozen=True)
class SignalCourtTrace:
    trace_id: str
    lane: str
    signal_id: str
    final_status: str
    blocked: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    steps: list[SignalCourtTraceStep]
    warnings: list[str]
    non_authorization_notice: str


def build_trace_from_pipeline_result(
    pipeline_result: SignalCourtPipelineResult,
) -> SignalCourtTrace:
    readiness = pipeline_result.readiness
    passport = pipeline_result.passport
    verdict = pipeline_result.verdict
    trade_decision = pipeline_result.trade_decision
    paper_decision = pipeline_result.paper_decision
    risk_gate = pipeline_result.risk_gate
    journal_entry = pipeline_result.journal_entry

    steps = [
        SignalCourtTraceStep(
            step_name="readiness",
            component="signalcourt.readiness",
            status=TRACE_BLOCKED_STATUS
            if (readiness.promotion_blocked or readiness.trade_decision_blocked)
            else TRACE_READY_STATUS,
            input_summary=(
                "artifacts="
                + str(len(readiness.source_artifacts))
                + f" lane={readiness.lane} signal_id={readiness.signal_id}"
            ),
            output_summary=(
                f"status={readiness.status} sim_ready={readiness.simulation_ready_count} "
                f"watchlist={readiness.watchlist_count} weak={readiness.weak_count} "
                f"rejected={readiness.rejected_count}"
            ),
            blockers=list(readiness.top_blockers),
            source_artifacts=list(readiness.source_artifacts),
            non_authorization_notice=readiness.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="passport",
            component="signalcourt.passport",
            status=TRACE_BLOCKED_STATUS if passport.trade_decision_blocked else TRACE_READY_STATUS,
            input_summary=(
                f"readiness_status={readiness.status} tradeable={readiness.tradeable} "
                f"research_only={readiness.research_only}"
            ),
            output_summary=(
                f"status={passport.status} readiness_status={passport.readiness_status} "
                f"tradeable={passport.tradeable} research_only={passport.research_only}"
            ),
            blockers=list(passport.top_blockers),
            source_artifacts=list(passport.source_artifacts),
            non_authorization_notice=passport.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="verdict",
            component="signalcourt.verdict",
            status=(
                TRACE_READY_STATUS
                if (verdict.promotion_allowed and verdict.trade_decision_allowed)
                else TRACE_BLOCKED_STATUS
            ),
            input_summary=(
                f"passport_status={passport.status} readiness_status={passport.readiness_status}"
            ),
            output_summary=(
                f"verdict={verdict.verdict} promotion_allowed={verdict.promotion_allowed} "
                f"trade_decision_allowed={verdict.trade_decision_allowed}"
            ),
            blockers=list(verdict.governance_blocks),
            source_artifacts=list(passport.source_artifacts),
            non_authorization_notice=verdict.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="trade_decision",
            component="signalcourt.decision",
            status=TRACE_BLOCKED_STATUS if not trade_decision.allowed else TRACE_READY_STATUS,
            input_summary=f"verdict={verdict.verdict} research_only={verdict.research_only}",
            output_summary=(
                f"action={trade_decision.action} execution_mode={trade_decision.execution_mode} "
                f"allowed={trade_decision.allowed}"
            ),
            blockers=list(trade_decision.blockers),
            source_artifacts=list(passport.source_artifacts),
            non_authorization_notice=trade_decision.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="paper_decision",
            component="signalcourt.paper_decision",
            status=TRACE_BLOCKED_STATUS if paper_decision.blocked else TRACE_READY_STATUS,
            input_summary=(
                f"requested_action={paper_decision.requested_action} "
                f"source_allowed={paper_decision.source_decision_allowed}"
            ),
            output_summary=(
                f"paper_action={paper_decision.paper_action} paper_allowed={paper_decision.paper_allowed} "
                f"blocked={paper_decision.blocked}"
            ),
            blockers=list(paper_decision.block_reasons),
            source_artifacts=list(passport.source_artifacts),
            non_authorization_notice=paper_decision.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="risk_gate",
            component="signalcourt.risk_gate",
            status=TRACE_BLOCKED_STATUS if risk_gate.blocked else TRACE_READY_STATUS,
            input_summary=(
                f"paper_action={paper_decision.paper_action} paper_allowed={paper_decision.paper_allowed}"
            ),
            output_summary=(
                f"risk_allowed={risk_gate.risk_allowed} paper_order_allowed={risk_gate.paper_order_allowed} "
                f"live_order_allowed={risk_gate.live_order_allowed} max_risk_usd={risk_gate.max_risk_usd:.2f}"
            ),
            blockers=list(risk_gate.block_reasons),
            source_artifacts=list(passport.source_artifacts),
            non_authorization_notice=risk_gate.non_authorization_notice,
        ),
        SignalCourtTraceStep(
            step_name="paper_journal",
            component="signalcourt.paper_journal",
            status=TRACE_BLOCKED_STATUS if journal_entry.blocked else TRACE_READY_STATUS,
            input_summary=(
                f"risk_allowed={risk_gate.risk_allowed} "
                f"paper_order_allowed={risk_gate.paper_order_allowed}"
            ),
            output_summary=(
                f"final_status={journal_entry.final_status} blocked={journal_entry.blocked} "
                f"paper_order_allowed={journal_entry.paper_order_allowed} "
                f"live_order_allowed={journal_entry.live_order_allowed}"
            ),
            blockers=list(journal_entry.block_reasons),
            source_artifacts=list(journal_entry.source_artifacts),
            non_authorization_notice=journal_entry.non_authorization_notice,
        ),
    ]

    warnings = _build_trace_warnings(steps=steps, pipeline_result=pipeline_result)
    trace_id = (
        f"{pipeline_result.signal_id}:{pipeline_result.lane}:"
        f"{pipeline_result.final_status}:trace_v1"
    )

    return SignalCourtTrace(
        trace_id=trace_id,
        lane=pipeline_result.lane,
        signal_id=pipeline_result.signal_id,
        final_status=pipeline_result.final_status,
        blocked=pipeline_result.blocked,
        paper_order_allowed=pipeline_result.paper_order_allowed,
        live_order_allowed=pipeline_result.live_order_allowed,
        steps=steps,
        warnings=warnings,
        non_authorization_notice=pipeline_result.non_authorization_notice,
    )


def trace_allows_order(trace: SignalCourtTrace) -> bool:
    if trace.blocked:
        return False
    if not trace.paper_order_allowed:
        return False
    if trace.live_order_allowed:
        return False
    if any(_is_blocking_status(step.status) for step in trace.steps):
        return False
    return True


def _is_blocking_status(status: str) -> bool:
    normalized = status.strip().upper()
    return normalized == TRACE_BLOCKED_STATUS or normalized.endswith("_BLOCKED")


def _build_trace_warnings(
    *,
    steps: list[SignalCourtTraceStep],
    pipeline_result: SignalCourtPipelineResult,
) -> list[str]:
    warnings: list[str] = []
    if pipeline_result.blocked:
        warnings.append("Pipeline remains blocked; execution is disabled.")
    if not pipeline_result.paper_order_allowed:
        warnings.append("No executable paper orders are currently allowed.")
    if not pipeline_result.live_order_allowed:
        warnings.append("Live trading is disabled in this phase.")
    blocked_steps = [step.step_name for step in steps if _is_blocking_status(step.status)]
    if blocked_steps:
        warnings.append("Blocked steps: " + ", ".join(blocked_steps))
    return warnings
