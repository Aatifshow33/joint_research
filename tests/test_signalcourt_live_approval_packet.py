from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.execution_adapter import evaluate_execution_adapter
from joint_research.signalcourt.live_approval_packet import (
    APPROVAL_STATUS_BLOCKED,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REVIEW_READY,
    LiveApprovalRequest,
    build_live_approval_packet,
)
from joint_research.signalcourt.micro_live_gate import (
    MicroLiveGatePolicy,
    build_micro_live_request,
    evaluate_micro_live_gate,
)
from joint_research.signalcourt.paper_fill_simulator import simulate_paper_fill
from joint_research.signalcourt.paper_order_preview import (
    PaperOrderRequest,
    build_paper_order_preview,
)
from joint_research.signalcourt.paper_performance_gate import review_paper_performance
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.readiness_bundle import (
    READINESS_VERDICT_MICRO_LIVE_REVIEW_READY,
    build_readiness_bundle,
)
from joint_research.signalcourt.risk_gate import (
    default_decision_preview_risk_policy,
    default_tiny_account_risk_config,
    evaluate_decision_preview_risk_gate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

DERIVATIVES_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/derivatives_regime"
DERIVATIVES_RESULTS_CSV = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_results.csv"
DERIVATIVES_CANDIDATES_JSON = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_candidates.json"
DERIVATIVES_SUMMARY_MD = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_summary.md"

WALLET_FLOW_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/wallet_flow_signal"
WALLET_FLOW_SIGNAL_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_summary.md"
WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV = (
    WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_diagnostics.csv"
)
WALLET_FLOW_REJECTION_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_summary.md"


def _build_wallet_bundle():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="wallet_live_approval_packet")
    decision_risk = evaluate_decision_preview_risk_gate(
        decision_preview,
        risk_policy=default_decision_preview_risk_policy(),
    )
    paper_order_preview = build_paper_order_preview(
        decision_preview,
        decision_risk,
        order_request=PaperOrderRequest(
            symbol="BTCUSD",
            side="BUY",
            quantity=0.01,
            limit_price=100.0,
            notional_usd=1.0,
            venue="paper_local",
            order_type="limit",
        ),
    )
    paper_fill = simulate_paper_fill(paper_order_preview)
    paper_performance = review_paper_performance([paper_fill])
    execution_result = evaluate_execution_adapter(
        preview=paper_order_preview,
        fill_result=paper_fill,
        performance_result=paper_performance,
    )
    micro_live_request = build_micro_live_request(
        performance_result=paper_performance,
        execution_result=execution_result,
        symbol=paper_order_preview.symbol,
        venue=paper_order_preview.venue,
        requested_notional_usd=paper_order_preview.notional_usd,
        order_type=paper_order_preview.order_type,
    )
    micro_live_result = evaluate_micro_live_gate(
        performance_result=paper_performance,
        execution_result=execution_result,
        request=micro_live_request,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=False,
            require_manual_approval=True,
            manual_approval_granted=False,
            kill_switch_enabled=True,
        ),
    )
    bundle = build_readiness_bundle(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=paper_fill,
        paper_performance_result=paper_performance,
        execution_adapter_result=execution_result,
        micro_live_gate_result=micro_live_result,
    )
    return pipeline, bundle


def _build_derivatives_bundle():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_live_approval_packet")
    decision_risk = evaluate_decision_preview_risk_gate(
        decision_preview,
        risk_policy=default_decision_preview_risk_policy(),
    )
    paper_order_preview = build_paper_order_preview(
        decision_preview,
        decision_risk,
        order_request=PaperOrderRequest(
            symbol="ETHUSD",
            side="BUY",
            quantity=0.02,
            limit_price=200.0,
            notional_usd=2.0,
            venue="paper_local",
            order_type="limit",
        ),
    )
    paper_fill = simulate_paper_fill(paper_order_preview)
    paper_performance = review_paper_performance([paper_fill])
    execution_result = evaluate_execution_adapter(
        preview=paper_order_preview,
        fill_result=paper_fill,
        performance_result=paper_performance,
    )
    micro_live_request = build_micro_live_request(
        performance_result=paper_performance,
        execution_result=execution_result,
        symbol=paper_order_preview.symbol,
        venue=paper_order_preview.venue,
        requested_notional_usd=paper_order_preview.notional_usd,
        order_type=paper_order_preview.order_type,
    )
    micro_live_result = evaluate_micro_live_gate(
        performance_result=paper_performance,
        execution_result=execution_result,
        request=micro_live_request,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=True,
            require_manual_approval=False,
            manual_approval_granted=True,
            kill_switch_enabled=False,
        ),
    )
    bundle = build_readiness_bundle(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=paper_fill,
        paper_performance_result=paper_performance,
        execution_adapter_result=execution_result,
        micro_live_gate_result=micro_live_result,
    )
    return pipeline, bundle


def _synthetic_review_ready_bundle():
    _, base_bundle = _build_derivatives_bundle()
    return replace(
        base_bundle,
        final_readiness_verdict=READINESS_VERDICT_MICRO_LIVE_REVIEW_READY,
        micro_live_review_ready=True,
        blocked_reasons=[],
        required_next_gates=[],
        micro_live_execution_allowed=False,
        live_execution_allowed=False,
        order_submitted=False,
        broker_call_performed=False,
        exchange_call_performed=False,
    )


def test_wallet_flow_blocked_readiness_returns_approval_blocked() -> None:
    _, bundle = _build_wallet_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.approval_status == APPROVAL_STATUS_BLOCKED


def test_derivatives_watch_only_readiness_returns_approval_blocked() -> None:
    _, bundle = _build_derivatives_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.approval_status == APPROVAL_STATUS_BLOCKED


def test_non_micro_live_ready_readiness_blocks_approval() -> None:
    _, bundle = _build_derivatives_bundle()
    non_ready = replace(bundle, final_readiness_verdict="PAPER_CHAIN_ONLY")
    packet = build_live_approval_packet(non_ready)
    assert packet.approval_status == APPROVAL_STATUS_BLOCKED


def test_micro_live_ready_without_manual_approval_returns_approval_pending() -> None:
    bundle = _synthetic_review_ready_bundle()
    packet = build_live_approval_packet(
        bundle,
        approval_request=LiveApprovalRequest(
            manual_approval_granted=False,
            operator_acknowledgement=False,
            approval_ttl_minutes=60,
        ),
    )
    assert packet.approval_status == APPROVAL_STATUS_PENDING


def test_micro_live_ready_with_manual_approval_and_ack_returns_review_ready_but_non_executable() -> None:
    bundle = _synthetic_review_ready_bundle()
    packet = build_live_approval_packet(
        bundle,
        approval_request=LiveApprovalRequest(
            manual_approval_granted=True,
            operator_acknowledgement=True,
            approval_ttl_minutes=60,
        ),
    )
    assert packet.approval_status == APPROVAL_STATUS_REVIEW_READY
    assert packet.micro_live_execution_allowed is False
    assert packet.live_execution_allowed is False
    assert packet.order_submitted is False
    assert packet.broker_call_performed is False
    assert packet.exchange_call_performed is False


def test_micro_live_execution_allowed_always_false() -> None:
    bundle = _synthetic_review_ready_bundle()
    packet = build_live_approval_packet(
        bundle,
        approval_request=LiveApprovalRequest(
            manual_approval_granted=True,
            operator_acknowledgement=True,
        ),
    )
    assert packet.micro_live_execution_allowed is False


def test_live_execution_allowed_always_false() -> None:
    bundle = _synthetic_review_ready_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.live_execution_allowed is False


def test_order_submitted_always_false() -> None:
    _, bundle = _build_wallet_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.order_submitted is False


def test_broker_exchange_flags_always_false() -> None:
    _, bundle = _build_wallet_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.broker_call_performed is False
    assert packet.exchange_call_performed is False


def test_packet_aggregates_blocked_reasons_and_required_next_gates() -> None:
    _, bundle = _build_wallet_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.blocked_reasons
    assert packet.required_next_gates
    assert any("readiness bundle verdict" in reason.lower() for reason in packet.blocked_reasons)
    assert any("resolve blocker:" in gate.lower() for gate in packet.required_next_gates)


def test_packet_includes_readiness_bundle() -> None:
    _, bundle = _build_derivatives_bundle()
    packet = build_live_approval_packet(bundle)
    assert packet.readiness_bundle == asdict(bundle)


def test_packet_includes_non_authorization_notice() -> None:
    _, bundle = _build_wallet_bundle()
    packet = build_live_approval_packet(bundle)
    lowered = packet.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_packet_safety_metadata_has_all_execution_flags_false() -> None:
    _, bundle = _build_derivatives_bundle()
    packet = build_live_approval_packet(bundle)
    safety = packet.approval_safety_metadata
    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["approval_packet_only"] is True
    assert safety["live_submit_command_available"] is False


def test_output_contains_no_broker_exchange_credential_fields() -> None:
    _, bundle = _build_derivatives_bundle()
    packet = build_live_approval_packet(bundle)
    payload_text = json.dumps(asdict(packet), sort_keys=True).lower()
    forbidden_tokens = [
        "api_key",
        "secret_key",
        "private_key",
        "access_token",
        "broker_token",
        "exchange_token",
    ]
    for token in forbidden_tokens:
        assert token not in payload_text


def test_output_is_deterministic() -> None:
    bundle = _synthetic_review_ready_bundle()
    request = LiveApprovalRequest(
        manual_approval_granted=True,
        operator_acknowledgement=True,
        approval_ttl_minutes=60,
        max_approved_notional_usd=100.0,
        requested_notional_usd=2.0,
    )
    first = build_live_approval_packet(bundle, approval_request=request)
    second = build_live_approval_packet(bundle, approval_request=request)
    assert first == second


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_bundle = _build_wallet_bundle()
    derivatives_pipeline, derivatives_bundle = _build_derivatives_bundle()
    wallet_packet = build_live_approval_packet(wallet_bundle)
    derivatives_packet = build_live_approval_packet(derivatives_bundle)

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_packet.micro_live_execution_allowed is False
    assert wallet_packet.live_execution_allowed is False
    assert wallet_packet.order_submitted is False
    assert derivatives_packet.micro_live_execution_allowed is False
    assert derivatives_packet.live_execution_allowed is False
    assert derivatives_packet.order_submitted is False
