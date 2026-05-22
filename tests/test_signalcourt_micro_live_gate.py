from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.execution_adapter import (
    ADAPTER_MODE_DRY_RUN,
    ADAPTER_MODE_LIVE_DISABLED,
    ExecutionAdapterPolicy,
    build_execution_request_from_preview,
    evaluate_execution_adapter,
)
from joint_research.signalcourt.micro_live_gate import (
    MICRO_LIVE_VERDICT_BLOCKED,
    MICRO_LIVE_VERDICT_KILL_SWITCH_BLOCKED,
    MICRO_LIVE_VERDICT_MANUAL_APPROVAL_REQUIRED,
    MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY,
    MICRO_LIVE_VERDICT_REVIEW_READY,
    MicroLiveGatePolicy,
    build_micro_live_request,
    default_micro_live_gate_policy,
    evaluate_micro_live_gate,
)
from joint_research.signalcourt.paper_fill_simulator import simulate_paper_fill
from joint_research.signalcourt.paper_order_preview import (
    PaperOrderRequest,
    build_paper_order_preview,
)
from joint_research.signalcourt.paper_performance_gate import (
    PERFORMANCE_VERDICT_CANDIDATE,
    PERFORMANCE_VERDICT_REVIEW_ONLY,
    review_paper_performance,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import (
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


def _build_wallet_inputs():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="wallet_micro_live_gate")
    risk_result = evaluate_decision_preview_risk_gate(decision_preview)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
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
    fill = simulate_paper_fill(paper_preview)
    performance = review_paper_performance([fill])
    execution = evaluate_execution_adapter(
        preview=paper_preview,
        fill_result=fill,
        performance_result=performance,
    )
    request = build_micro_live_request(
        performance_result=performance,
        execution_result=execution,
        symbol=paper_preview.symbol,
        venue=paper_preview.venue,
        requested_notional_usd=paper_preview.notional_usd,
        order_type=paper_preview.order_type,
    )
    return pipeline, performance, execution, request


def _build_derivatives_inputs():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_micro_live_gate")
    risk_result = evaluate_decision_preview_risk_gate(decision_preview)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
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
    fill = simulate_paper_fill(paper_preview)
    performance = review_paper_performance([fill])
    execution = evaluate_execution_adapter(
        preview=paper_preview,
        fill_result=fill,
        performance_result=performance,
    )
    request = build_micro_live_request(
        performance_result=performance,
        execution_result=execution,
        symbol=paper_preview.symbol,
        venue=paper_preview.venue,
        requested_notional_usd=paper_preview.notional_usd,
        order_type=paper_preview.order_type,
    )
    return pipeline, performance, execution, request


def test_default_policy_blocks_micro_live() -> None:
    _, performance, execution, request = _build_wallet_inputs()
    policy = default_micro_live_gate_policy()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert result.micro_live_execution_allowed is False
    assert result.live_execution_allowed is False


def test_wallet_flow_blocked_path_returns_micro_live_blocked() -> None:
    _, performance, execution, request = _build_wallet_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert result.micro_live_verdict == MICRO_LIVE_VERDICT_BLOCKED
    assert result.micro_live_execution_allowed is False
    assert result.live_execution_allowed is False


def test_derivatives_watch_only_path_remains_non_executable() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert result.micro_live_verdict in {MICRO_LIVE_VERDICT_BLOCKED, MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY}
    assert result.micro_live_execution_allowed is False
    assert result.live_execution_allowed is False


def test_kill_switch_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=MicroLiveGatePolicy(kill_switch_enabled=True),
        request=request,
    )
    assert result.micro_live_verdict == MICRO_LIVE_VERDICT_KILL_SWITCH_BLOCKED


def test_micro_live_disabled_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=False,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert any("micro-live is disabled" in reason for reason in result.blocked_reasons)


def test_missing_manual_approval_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=True,
        manual_approval_granted=False,
        kill_switch_enabled=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert result.micro_live_verdict == MICRO_LIVE_VERDICT_MANUAL_APPROVAL_REQUIRED


def test_max_notional_breach_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        max_micro_live_notional_usd=0.5,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert any("requested notional" in reason for reason in result.blocked_reasons)


def test_non_allowlisted_symbol_or_venue_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        allowlisted_symbols=("BTCUSD",),
        allowlisted_venues=("venue_a",),
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert any("not allowlisted" in reason for reason in result.blocked_reasons)


def test_market_orders_blocked_when_disallowed() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    market_request = replace(request, order_type="market")
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        allow_market_orders=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=market_request,
    )
    assert any("market orders are disabled" in reason for reason in result.blocked_reasons)


def test_leverage_blocked_when_disallowed() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    leverage_request = replace(request, leverage_requested=True)
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        allow_leverage=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=policy,
        request=leverage_request,
    )
    assert any("leverage is disabled" in reason for reason in result.blocked_reasons)


def test_execution_adapter_order_or_broker_or_exchange_flags_block() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    forced_execution = replace(
        execution,
        order_submitted=True,
        broker_call_performed=True,
        exchange_call_performed=True,
    )
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=forced_execution,
        policy=policy,
        request=request,
    )
    assert any("execution adapter indicates order was submitted" in reason for reason in result.blocked_reasons)


def test_non_candidate_paper_performance_blocks() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    non_candidate = replace(performance, performance_verdict=PERFORMANCE_VERDICT_REVIEW_ONLY)
    policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=False,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        require_paper_candidate=True,
    )
    result = evaluate_micro_live_gate(
        performance_result=non_candidate,
        execution_result=execution,
        policy=policy,
        request=request,
    )
    assert any("not a paper candidate" in reason for reason in result.blocked_reasons)


def test_synthetic_all_gates_pass_can_return_review_ready_but_execution_stays_false() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    ready_performance = replace(
        performance,
        performance_verdict=PERFORMANCE_VERDICT_CANDIDATE,
        blocked_reasons=[],
    )
    safe_execution = replace(
        execution,
        adapter_mode=ADAPTER_MODE_LIVE_DISABLED,
        requested_mode=ADAPTER_MODE_DRY_RUN,
        blocked_reasons=[],
        order_submitted=False,
        broker_call_performed=False,
        exchange_call_performed=False,
        paper_execution_allowed=False,
        live_execution_allowed=False,
    )
    pass_policy = MicroLiveGatePolicy(
        micro_live_enabled=True,
        require_manual_approval=True,
        manual_approval_granted=True,
        kill_switch_enabled=False,
        max_micro_live_notional_usd=10.0,
        allowlisted_symbols=("ETHUSD",),
        allowlisted_venues=("paper_local",),
        allow_market_orders=False,
        allow_leverage=False,
        require_paper_candidate=True,
        require_execution_adapter_live_disabled=True,
        require_no_execution_flags=True,
        require_golden_evaluations=True,
        require_operator_acknowledgement=False,
    )
    result = evaluate_micro_live_gate(
        performance_result=ready_performance,
        execution_result=safe_execution,
        policy=pass_policy,
        request=request,
    )
    assert result.micro_live_verdict == MICRO_LIVE_VERDICT_REVIEW_READY
    assert result.micro_live_review_ready is True
    assert result.micro_live_execution_allowed is False
    assert result.live_execution_allowed is False


def test_micro_live_execution_allowed_always_false() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=True,
            require_manual_approval=False,
            manual_approval_granted=True,
            kill_switch_enabled=False,
        ),
        request=request,
    )
    assert result.micro_live_execution_allowed is False


def test_live_execution_allowed_always_false() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=True,
            require_manual_approval=False,
            manual_approval_granted=True,
            kill_switch_enabled=False,
        ),
        request=request,
    )
    assert result.live_execution_allowed is False


def test_gate_includes_blocked_reasons_and_required_next_gates() -> None:
    _, performance, execution, request = _build_wallet_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=request,
    )
    assert result.blocked_reasons
    assert result.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in result.required_next_gates)


def test_gate_includes_non_authorization_notice() -> None:
    _, performance, execution, request = _build_wallet_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=request,
    )
    lowered = result.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_safety_metadata_has_all_execution_flags_false() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=request,
    )
    safety = result.gate_safety_metadata
    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["micro_live_gate_only"] is True
    assert safety["live_submit_command_available"] is False


def test_output_contains_no_broker_exchange_live_order_submission_payloads() -> None:
    _, performance, execution, request = _build_derivatives_inputs()
    result = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=request,
    )
    payload_text = json.dumps(asdict(result), sort_keys=True).lower()
    forbidden_terms = [
        "broker_api",
        "exchange_api",
        "submit_live_order",
        "place_live_order",
        "live_execution_payload",
    ]
    for term in forbidden_terms:
        assert term not in payload_text


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_performance, wallet_execution, wallet_request = _build_wallet_inputs()
    derivatives_pipeline, derivatives_performance, derivatives_execution, derivatives_request = (
        _build_derivatives_inputs()
    )
    wallet_result = evaluate_micro_live_gate(
        performance_result=wallet_performance,
        execution_result=wallet_execution,
        request=wallet_request,
    )
    derivatives_result = evaluate_micro_live_gate(
        performance_result=derivatives_performance,
        execution_result=derivatives_execution,
        request=derivatives_request,
    )
    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_result.micro_live_execution_allowed is False
    assert wallet_result.live_execution_allowed is False
    assert derivatives_result.micro_live_execution_allowed is False
    assert derivatives_result.live_execution_allowed is False
