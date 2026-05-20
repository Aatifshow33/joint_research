from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.execution_adapter import (
    ADAPTER_MODE_DRY_RUN,
    ADAPTER_MODE_LIVE_DISABLED,
    EXECUTION_VERDICT_KILL_SWITCH_BLOCKED,
    EXECUTION_VERDICT_LIVE_DISABLED,
    EXECUTION_VERDICT_MANUAL_APPROVAL_REQUIRED,
    ExecutionAdapterPolicy,
    build_execution_request_from_preview,
    default_execution_adapter_policy,
    evaluate_execution_adapter,
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
    decision_preview = build_decision_preview(pipeline, run_id="wallet_execution_adapter")
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
    return pipeline, paper_preview, fill, performance


def _build_derivatives_inputs():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_execution_adapter")
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
    return pipeline, paper_preview, fill, performance


def test_default_adapter_policy_is_live_disabled() -> None:
    policy = default_execution_adapter_policy()
    assert policy.adapter_mode == ADAPTER_MODE_LIVE_DISABLED
    assert policy.live_trading_enabled is False


def test_live_execution_allowed_is_always_false_in_this_phase() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    permissive_policy = ExecutionAdapterPolicy(
        live_trading_enabled=True,
        paper_trading_enabled=True,
        require_manual_approval=False,
        kill_switch_enabled=False,
        max_notional_usd=100.0,
        allowlisted_symbols=(),
        allowlisted_venues=(),
        allow_market_orders=True,
        allow_leverage=False,
        adapter_mode=ADAPTER_MODE_DRY_RUN,
    )
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        policy=permissive_policy,
    )
    assert result.live_execution_allowed is False


def test_order_submitted_is_always_false() -> None:
    _, preview, fill, performance = _build_wallet_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    assert result.order_submitted is False


def test_broker_and_exchange_flags_are_always_false() -> None:
    _, preview, fill, performance = _build_wallet_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    assert result.broker_call_performed is False
    assert result.exchange_call_performed is False


def test_kill_switch_blocks_all_execution() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    policy = ExecutionAdapterPolicy(
        live_trading_enabled=True,
        paper_trading_enabled=True,
        require_manual_approval=False,
        kill_switch_enabled=True,
        max_notional_usd=100.0,
        allowlisted_symbols=(),
        allowlisted_venues=(),
        allow_market_orders=True,
        allow_leverage=False,
        adapter_mode=ADAPTER_MODE_DRY_RUN,
    )
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        policy=policy,
    )
    assert result.execution_verdict == EXECUTION_VERDICT_KILL_SWITCH_BLOCKED


def test_live_trading_disabled_blocks_live() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    policy = ExecutionAdapterPolicy(
        live_trading_enabled=False,
        paper_trading_enabled=True,
        require_manual_approval=False,
        kill_switch_enabled=False,
        max_notional_usd=100.0,
        allowlisted_symbols=(),
        allowlisted_venues=(),
        allow_market_orders=True,
        allow_leverage=False,
        adapter_mode=ADAPTER_MODE_DRY_RUN,
    )
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        policy=policy,
    )
    assert result.execution_verdict == EXECUTION_VERDICT_LIVE_DISABLED


def test_manual_approval_requirement_blocks_live() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    policy = ExecutionAdapterPolicy(
        live_trading_enabled=True,
        paper_trading_enabled=True,
        require_manual_approval=True,
        kill_switch_enabled=False,
        max_notional_usd=100.0,
        allowlisted_symbols=(),
        allowlisted_venues=(),
        allow_market_orders=True,
        allow_leverage=False,
        adapter_mode=ADAPTER_MODE_DRY_RUN,
    )
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        policy=policy,
    )
    assert result.execution_verdict == EXECUTION_VERDICT_MANUAL_APPROVAL_REQUIRED


def test_wallet_flow_blocked_path_remains_non_executable() -> None:
    pipeline, preview, fill, performance = _build_wallet_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    assert pipeline_allows_order(pipeline) is False
    assert result.paper_execution_allowed is False
    assert result.live_execution_allowed is False
    assert result.order_submitted is False


def test_derivatives_watch_only_path_remains_non_executable() -> None:
    pipeline, preview, fill, performance = _build_derivatives_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    assert pipeline_allows_order(pipeline) is False
    assert result.paper_execution_allowed is False
    assert result.live_execution_allowed is False
    assert result.order_submitted is False


def test_adapter_includes_blocked_reasons_and_required_next_gates() -> None:
    _, preview, fill, performance = _build_wallet_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    assert result.blocked_reasons
    assert result.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in result.required_next_gates)
    assert any("live-disabled mode" in gate.lower() for gate in result.required_next_gates)


def test_adapter_includes_non_authorization_notice() -> None:
    _, preview, fill, performance = _build_wallet_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    lowered = result.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_adapter_safety_metadata_has_all_execution_flags_false() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
    )
    safety = result.adapter_safety_metadata
    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["live_disabled_by_default"] is True


def test_adapter_output_contains_no_broker_exchange_live_order_payload_terms() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    result = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
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
    wallet_pipeline, wallet_preview, wallet_fill, wallet_performance = _build_wallet_inputs()
    derivatives_pipeline, derivatives_preview, derivatives_fill, derivatives_performance = (
        _build_derivatives_inputs()
    )

    wallet_result = evaluate_execution_adapter(
        preview=wallet_preview,
        fill_result=wallet_fill,
        performance_result=wallet_performance,
    )
    derivatives_result = evaluate_execution_adapter(
        preview=derivatives_preview,
        fill_result=derivatives_fill,
        performance_result=derivatives_performance,
    )

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_result.paper_execution_allowed is False
    assert wallet_result.live_execution_allowed is False
    assert derivatives_result.paper_execution_allowed is False
    assert derivatives_result.live_execution_allowed is False


def test_adapter_is_deterministic() -> None:
    _, preview, fill, performance = _build_derivatives_inputs()
    request = build_execution_request_from_preview(preview, requested_mode=ADAPTER_MODE_DRY_RUN)
    first = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        request=request,
    )
    second = evaluate_execution_adapter(
        preview=preview,
        fill_result=fill,
        performance_result=performance,
        request=request,
    )
    assert first == second
