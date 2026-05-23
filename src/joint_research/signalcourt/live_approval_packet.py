"""SignalCourt micro-live approval packet builder (non-executing)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from joint_research.signalcourt.readiness_bundle import (
    READINESS_VERDICT_MICRO_LIVE_REVIEW_READY,
    SignalCourtReadinessBundle,
)

APPROVAL_STATUS_BLOCKED = "APPROVAL_BLOCKED"
APPROVAL_STATUS_PENDING = "APPROVAL_PENDING"
APPROVAL_STATUS_REVIEW_READY = "APPROVAL_REVIEW_READY"
APPROVAL_STATUS_EXPIRED = "APPROVAL_EXPIRED"
APPROVAL_STATUS_REVOKED = "APPROVAL_REVOKED"

_NON_AUTH_NOTICE = (
    "Live approval packet is non-executing and does not authorize paper/live trading, "
    "order placement, broker calls, exchange calls, API/LLM calls, or execution."
)


@dataclass(frozen=True)
class LiveApprovalRequest:
    requested_by: str = "local_operator"
    operator_acknowledgement: bool = False
    manual_approval_granted: bool = False
    approval_note: str = ""
    approval_ttl_minutes: int = 60
    max_approved_notional_usd: float = 0.0
    requested_notional_usd: float = 0.0


@dataclass(frozen=True)
class SignalCourtLiveApprovalPacket:
    approval_packet_id: str
    run_id: str
    lane: str
    symbol: str
    venue: str
    requested_notional_usd: float
    readiness_verdict: str
    approval_status: str
    manual_approval_required: bool
    manual_approval_granted: bool
    operator_acknowledgement: bool
    approval_ttl_minutes: int
    max_approved_notional_usd: float
    micro_live_review_ready: bool
    micro_live_execution_allowed: bool
    live_execution_allowed: bool
    order_submitted: bool
    broker_call_performed: bool
    exchange_call_performed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    readiness_bundle: dict[str, object]
    approval_safety_metadata: dict[str, bool]
    non_authorization_notice: str


def build_live_approval_packet(
    readiness_bundle: SignalCourtReadinessBundle,
    *,
    approval_request: LiveApprovalRequest | None = None,
) -> SignalCourtLiveApprovalPacket:
    request = approval_request or LiveApprovalRequest()
    requested_notional_usd = float(request.requested_notional_usd)
    max_approved_notional_usd = float(request.max_approved_notional_usd)

    blocked_reasons = _collect_blocked_reasons(
        readiness_bundle=readiness_bundle,
        request=request,
        requested_notional_usd=requested_notional_usd,
        max_approved_notional_usd=max_approved_notional_usd,
    )
    required_next_gates = _collect_required_next_gates(
        readiness_bundle=readiness_bundle,
        blocked_reasons=blocked_reasons,
    )
    approval_status = _select_approval_status(
        readiness_bundle=readiness_bundle,
        request=request,
        blocked_reasons=blocked_reasons,
    )
    packet_id = _build_approval_packet_id(
        run_id=readiness_bundle.run_id,
        lane=readiness_bundle.lane,
        symbol=readiness_bundle.symbol,
        venue=readiness_bundle.venue,
        readiness_verdict=readiness_bundle.final_readiness_verdict,
        approval_status=approval_status,
        requested_notional_usd=requested_notional_usd,
        max_approved_notional_usd=max_approved_notional_usd,
        operator_acknowledgement=request.operator_acknowledgement,
        manual_approval_granted=request.manual_approval_granted,
        approval_ttl_minutes=request.approval_ttl_minutes,
    )

    # Hard-off in this phase: this packet cannot authorize execution.
    micro_live_execution_allowed = False
    live_execution_allowed = False
    order_submitted = False
    broker_call_performed = False
    exchange_call_performed = False

    notice = (
        f"{readiness_bundle.non_authorization_notice} {_NON_AUTH_NOTICE}"
    ).strip()

    return SignalCourtLiveApprovalPacket(
        approval_packet_id=packet_id,
        run_id=readiness_bundle.run_id,
        lane=readiness_bundle.lane,
        symbol=readiness_bundle.symbol,
        venue=readiness_bundle.venue,
        requested_notional_usd=requested_notional_usd,
        readiness_verdict=readiness_bundle.final_readiness_verdict,
        approval_status=approval_status,
        manual_approval_required=True,
        manual_approval_granted=bool(request.manual_approval_granted),
        operator_acknowledgement=bool(request.operator_acknowledgement),
        approval_ttl_minutes=int(request.approval_ttl_minutes),
        max_approved_notional_usd=max_approved_notional_usd,
        micro_live_review_ready=bool(
            readiness_bundle.final_readiness_verdict
            == READINESS_VERDICT_MICRO_LIVE_REVIEW_READY
        ),
        micro_live_execution_allowed=micro_live_execution_allowed,
        live_execution_allowed=live_execution_allowed,
        order_submitted=order_submitted,
        broker_call_performed=broker_call_performed,
        exchange_call_performed=exchange_call_performed,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        readiness_bundle=asdict(readiness_bundle),
        approval_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "approval_packet_only": True,
            "live_submit_command_available": False,
        },
        non_authorization_notice=notice,
    )


def _collect_blocked_reasons(
    *,
    readiness_bundle: SignalCourtReadinessBundle,
    request: LiveApprovalRequest,
    requested_notional_usd: float,
    max_approved_notional_usd: float,
) -> list[str]:
    reasons = list(readiness_bundle.blocked_reasons)

    if request.approval_ttl_minutes <= 0:
        reasons.append("approval TTL has expired")
    if _request_is_revoked(request):
        reasons.append("approval request was revoked by operator note")
    if (
        readiness_bundle.final_readiness_verdict
        != READINESS_VERDICT_MICRO_LIVE_REVIEW_READY
    ):
        reasons.append(
            "readiness bundle verdict is not MICRO_LIVE_REVIEW_READY"
        )
    if not request.manual_approval_granted:
        reasons.append("manual approval has not been granted")
    if not request.operator_acknowledgement:
        reasons.append("operator acknowledgement has not been provided")
    if max_approved_notional_usd > 0 and requested_notional_usd > max_approved_notional_usd:
        reasons.append(
            f"requested notional {requested_notional_usd:.4f} exceeds max approved "
            f"{max_approved_notional_usd:.4f}"
        )
    if readiness_bundle.micro_live_execution_allowed:
        reasons.append("upstream readiness bundle indicates micro-live execution allowed")
    if readiness_bundle.live_execution_allowed:
        reasons.append("upstream readiness bundle indicates live execution allowed")
    if readiness_bundle.order_submitted:
        reasons.append("upstream readiness bundle indicates order submitted")
    if readiness_bundle.broker_call_performed:
        reasons.append("upstream readiness bundle indicates broker call performed")
    if readiness_bundle.exchange_call_performed:
        reasons.append("upstream readiness bundle indicates exchange call performed")

    return list(dict.fromkeys(reason for reason in reasons if reason))


def _collect_required_next_gates(
    *,
    readiness_bundle: SignalCourtReadinessBundle,
    blocked_reasons: list[str],
) -> list[str]:
    gates = [
        *readiness_bundle.required_next_gates,
        "Maintain non-executing posture: no paper/live execution in this phase.",
        "Require explicit future live-submit command gating before any execution can exist.",
        "Keep golden evaluations passing.",
    ]
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    return list(dict.fromkeys(gate for gate in gates if gate))


def _select_approval_status(
    *,
    readiness_bundle: SignalCourtReadinessBundle,
    request: LiveApprovalRequest,
    blocked_reasons: list[str],
) -> str:
    if _request_is_revoked(request):
        return APPROVAL_STATUS_REVOKED
    if request.approval_ttl_minutes <= 0:
        return APPROVAL_STATUS_EXPIRED
    if (
        readiness_bundle.final_readiness_verdict
        != READINESS_VERDICT_MICRO_LIVE_REVIEW_READY
    ):
        return APPROVAL_STATUS_BLOCKED
    if any(
        token in reason.lower()
        for reason in blocked_reasons
        for token in (
            "execution allowed",
            "order submitted",
            "broker call",
            "exchange call",
        )
    ):
        return APPROVAL_STATUS_BLOCKED
    if request.manual_approval_granted and request.operator_acknowledgement:
        return APPROVAL_STATUS_REVIEW_READY
    return APPROVAL_STATUS_PENDING


def _request_is_revoked(request: LiveApprovalRequest) -> bool:
    lowered = request.approval_note.strip().lower()
    return lowered.startswith("revoked") or lowered.startswith("revoke:")


def _build_approval_packet_id(
    *,
    run_id: str,
    lane: str,
    symbol: str,
    venue: str,
    readiness_verdict: str,
    approval_status: str,
    requested_notional_usd: float,
    max_approved_notional_usd: float,
    operator_acknowledgement: bool,
    manual_approval_granted: bool,
    approval_ttl_minutes: int,
) -> str:
    payload = json.dumps(
        {
            "run_id": run_id,
            "lane": lane,
            "symbol": symbol,
            "venue": venue,
            "readiness_verdict": readiness_verdict,
            "approval_status": approval_status,
            "requested_notional_usd": float(requested_notional_usd),
            "max_approved_notional_usd": float(max_approved_notional_usd),
            "operator_acknowledgement": bool(operator_acknowledgement),
            "manual_approval_granted": bool(manual_approval_granted),
            "approval_ttl_minutes": int(approval_ttl_minutes),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"approval_packet_{digest[:16]}"
