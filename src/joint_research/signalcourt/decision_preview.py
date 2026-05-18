"""Deterministic non-executing SignalCourt decision preview object."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.paper_journal import PaperJournalEntry
from joint_research.signalcourt.pipeline import SignalCourtPipelineResult

ACTION_NO_TRADE = "NO_TRADE"
ACTION_WATCH_ONLY = "WATCH_ONLY"
ACTION_PAPER_REVIEW_CANDIDATE = "PAPER_REVIEW_CANDIDATE"
ACTION_PAPER_BLOCKED = "PAPER_BLOCKED"
ACTION_LIVE_BLOCKED = "LIVE_BLOCKED"

_NON_AUTH_NOTICE = (
    "Decision preview is non-executing and does not authorize paper/live trading, "
    "order placement, or execution."
)


@dataclass(frozen=True)
class SignalCourtDecisionPreview:
    run_id: str
    lane: str
    verdict: str
    final_status: str
    decision_action: str
    paper_eligible: bool
    live_eligible: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    evidence_summary: str
    non_authorization_notice: str


def build_decision_preview(
    evidence: SignalCourtPipelineResult | PaperJournalEntry,
    *,
    run_id: str | None = None,
) -> SignalCourtDecisionPreview:
    lane = evidence.lane
    final_status = evidence.final_status
    verdict = _get_verdict(evidence)
    blocked = evidence.blocked
    paper_order_allowed = evidence.paper_order_allowed
    live_order_allowed = evidence.live_order_allowed
    trade_action = _get_trade_action(evidence)
    reasons = _collect_blocked_reasons(evidence)

    decision_action = _map_decision_action(
        blocked=blocked,
        final_status=final_status,
        trade_action=trade_action,
        paper_order_allowed=paper_order_allowed,
        live_order_allowed=live_order_allowed,
    )
    paper_eligible = bool(
        not blocked
        and paper_order_allowed
        and decision_action == ACTION_PAPER_REVIEW_CANDIDATE
    )
    # Live eligibility remains hard-blocked in this phase.
    live_eligible = False
    preview_run_id = run_id or _default_run_id(evidence)
    next_gates = _required_next_gates(
        blocked=blocked,
        paper_eligible=paper_eligible,
        blocked_reasons=reasons,
    )
    evidence_summary = (
        f"lane={lane} verdict={verdict} final_status={final_status} "
        f"blocked={blocked} paper_order_allowed={paper_order_allowed} "
        f"live_order_allowed={live_order_allowed}"
    )

    source_notice = evidence.non_authorization_notice
    combined_notice = f"{source_notice} {_NON_AUTH_NOTICE}".strip()

    return SignalCourtDecisionPreview(
        run_id=preview_run_id,
        lane=lane,
        verdict=verdict,
        final_status=final_status,
        decision_action=decision_action,
        paper_eligible=paper_eligible,
        live_eligible=live_eligible,
        blocked_reasons=reasons,
        required_next_gates=next_gates,
        evidence_summary=evidence_summary,
        non_authorization_notice=combined_notice,
    )


def _map_decision_action(
    *,
    blocked: bool,
    final_status: str,
    trade_action: str,
    paper_order_allowed: bool,
    live_order_allowed: bool,
) -> str:
    if blocked:
        if final_status == "WATCH_ONLY_BLOCKED" or trade_action == ACTION_WATCH_ONLY:
            return ACTION_WATCH_ONLY
        if final_status == "NO_TRADE_BLOCKED" or trade_action == ACTION_NO_TRADE:
            return ACTION_NO_TRADE
        return ACTION_PAPER_BLOCKED
    if live_order_allowed:
        return ACTION_LIVE_BLOCKED
    if paper_order_allowed:
        return ACTION_PAPER_REVIEW_CANDIDATE
    if trade_action == ACTION_WATCH_ONLY:
        return ACTION_WATCH_ONLY
    return ACTION_NO_TRADE


def _required_next_gates(
    *,
    blocked: bool,
    paper_eligible: bool,
    blocked_reasons: list[str],
) -> list[str]:
    gates: list[str] = []
    if blocked:
        gates.append("Maintain blocked/no-trade posture until explicit future gates are approved.")
    if not paper_eligible:
        gates.append("Paper eligibility remains disabled until explicit paper gates are implemented.")
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    gates.append("Keep golden evaluations passing.")
    # Dedupe while keeping deterministic order.
    return list(dict.fromkeys(gates))


def _collect_blocked_reasons(evidence: SignalCourtPipelineResult | PaperJournalEntry) -> list[str]:
    reasons = list(evidence.block_reasons) if isinstance(evidence, PaperJournalEntry) else list(
        evidence.journal_entry.block_reasons
    )
    if isinstance(evidence, SignalCourtPipelineResult):
        reasons.extend(evidence.verdict.governance_blocks)
    return list(dict.fromkeys(reason for reason in reasons if reason))


def _get_trade_action(evidence: SignalCourtPipelineResult | PaperJournalEntry) -> str:
    if isinstance(evidence, PaperJournalEntry):
        return evidence.trade_action
    return evidence.trade_decision.action


def _get_verdict(evidence: SignalCourtPipelineResult | PaperJournalEntry) -> str:
    if isinstance(evidence, PaperJournalEntry):
        return evidence.verdict
    return evidence.verdict.verdict


def _default_run_id(evidence: SignalCourtPipelineResult | PaperJournalEntry) -> str:
    signal_id = evidence.signal_id
    return f"{signal_id}:{evidence.lane}:{evidence.final_status}:decision_preview_v1"
