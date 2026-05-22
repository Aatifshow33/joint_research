from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.execution_adapter import (
    ADAPTER_MODE_LIVE_DISABLED,
    evaluate_execution_adapter,
)
from joint_research.signalcourt.micro_live_gate import (
    MICRO_LIVE_VERDICT_BLOCKED,
    MICRO_LIVE_VERDICT_REVIEW_READY,
    MicroLiveGatePolicy,
    build_micro_live_request,
    evaluate_micro_live_gate,
)
from joint_research.signalcourt.paper_fill_simulator import simulate_paper_fill
from joint_research.signalcourt.paper_order_preview import (
    PaperOrderRequest,
    build_paper_order_preview,
)
from joint_research.signalcourt.paper_performance_gate import (
    PERFORMANCE_VERDICT_CANDIDATE,
    review_paper_performance,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.readiness_bundle import (
    READINESS_VERDICT_BLOCKED,
    READINESS_VERDICT_MICRO_LIVE_REVIEW_READY,
    READINESS_VERDICT_PAPER_CHAIN_ONLY,
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


def _build_wallet_chain():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="wallet_readiness_bundle")
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
    fill = simulate_paper_fill(paper_order_preview)
    performance = review_paper_performance([fill])
    execution = evaluate_execution_adapter(
        preview=paper_order_preview,
        fill_result=fill,
        performance_result=performance,
    )
    micro_live_request = build_micro_live_request(
        performance_result=performance,
        execution_result=execution,
        symbol=paper_order_preview.symbol,
        venue=paper_order_preview.venue,
        requested_notional_usd=paper_order_preview.notional_usd,
        order_type=paper_order_preview.order_type,
    )
    micro_live = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=micro_live_request,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=False,
            require_manual_approval=True,
            manual_approval_granted=False,
            kill_switch_enabled=True,
        ),
    )
    return (
        pipeline,
        decision_preview,
        decision_risk,
        paper_order_preview,
        fill,
        performance,
        execution,
        micro_live,
    )


def _build_derivatives_chain():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_readiness_bundle")
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
    fill = simulate_paper_fill(paper_order_preview)
    performance = review_paper_performance([fill])
    execution = evaluate_execution_adapter(
        preview=paper_order_preview,
        fill_result=fill,
        performance_result=performance,
    )
    micro_live_request = build_micro_live_request(
        performance_result=performance,
        execution_result=execution,
        symbol=paper_order_preview.symbol,
        venue=paper_order_preview.venue,
        requested_notional_usd=paper_order_preview.notional_usd,
        order_type=paper_order_preview.order_type,
    )
    micro_live = evaluate_micro_live_gate(
        performance_result=performance,
        execution_result=execution,
        request=micro_live_request,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=True,
            require_manual_approval=False,
            manual_approval_granted=True,
            kill_switch_enabled=False,
        ),
    )
    return (
        pipeline,
        decision_preview,
        decision_risk,
        paper_order_preview,
        fill,
        performance,
        execution,
        micro_live,
    )


def _bundle_from_chain(chain):
    (
        _pipeline,
        decision_preview,
        decision_risk,
        paper_order_preview,
        fill,
        performance,
        execution,
        micro_live,
    ) = chain
    return build_readiness_bundle(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=fill,
        paper_performance_result=performance,
        execution_adapter_result=execution,
        micro_live_gate_result=micro_live,
    )


def test_wallet_flow_blocked_path_returns_readiness_blocked() -> None:
    bundle = _bundle_from_chain(_build_wallet_chain())
    assert bundle.final_readiness_verdict == READINESS_VERDICT_BLOCKED


def test_derivatives_watch_only_path_remains_non_executable_and_not_micro_live_ready() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    assert bundle.final_readiness_verdict in {READINESS_VERDICT_BLOCKED, READINESS_VERDICT_PAPER_CHAIN_ONLY}
    assert bundle.micro_live_review_ready is False
    assert bundle.micro_live_execution_allowed is False
    assert bundle.live_execution_allowed is False


def test_micro_live_execution_allowed_always_false() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    assert bundle.micro_live_execution_allowed is False


def test_live_execution_allowed_always_false() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    assert bundle.live_execution_allowed is False


def test_order_submitted_always_false() -> None:
    bundle = _bundle_from_chain(_build_wallet_chain())
    assert bundle.order_submitted is False


def test_broker_exchange_flags_always_false() -> None:
    bundle = _bundle_from_chain(_build_wallet_chain())
    assert bundle.broker_call_performed is False
    assert bundle.exchange_call_performed is False


def test_unsafe_upstream_execution_flags_block_readiness() -> None:
    chain = _build_derivatives_chain()
    modified_execution = replace(chain[6], order_submitted=True, broker_call_performed=True, exchange_call_performed=True)
    bundle = build_readiness_bundle(
        decision_preview=chain[1],
        decision_risk=chain[2],
        paper_order_preview=chain[3],
        paper_fill_result=chain[4],
        paper_performance_result=chain[5],
        execution_adapter_result=modified_execution,
        micro_live_gate_result=chain[7],
    )
    assert bundle.final_readiness_verdict == READINESS_VERDICT_BLOCKED
    assert any("order submitted" in reason.lower() for reason in bundle.blocked_reasons)


def test_non_ready_micro_live_gate_blocks_micro_live_readiness() -> None:
    chain = _build_derivatives_chain()
    modified_micro = replace(chain[7], micro_live_verdict=MICRO_LIVE_VERDICT_BLOCKED)
    bundle = build_readiness_bundle(
        decision_preview=chain[1],
        decision_risk=chain[2],
        paper_order_preview=chain[3],
        paper_fill_result=chain[4],
        paper_performance_result=chain[5],
        execution_adapter_result=chain[6],
        micro_live_gate_result=modified_micro,
    )
    assert bundle.micro_live_review_ready is False


def test_synthetic_all_gates_pass_may_return_micro_live_review_ready_with_execution_flags_false() -> None:
    chain = _build_derivatives_chain()
    safe_fill_meta = dict(chain[4].simulator_safety_metadata)
    safe_perf_meta = dict(chain[5].review_safety_metadata)
    safe_exec_meta = dict(chain[6].adapter_safety_metadata)
    safe_micro_meta = dict(chain[7].gate_safety_metadata)
    for key in safe_fill_meta:
        safe_fill_meta[key] = False if key != "simulation_only" else True
    for key in safe_perf_meta:
        safe_perf_meta[key] = False if key != "review_only" else True
    for key in safe_exec_meta:
        safe_exec_meta[key] = False if key != "live_disabled_by_default" else True
    for key in safe_micro_meta:
        safe_micro_meta[key] = False if key not in {"micro_live_gate_only"} else True
    safe_micro_meta["live_submit_command_available"] = False

    synthetic_fill = replace(chain[4], blocked_reasons=[], required_next_gates=[], simulator_safety_metadata=safe_fill_meta)
    synthetic_perf = replace(
        chain[5],
        performance_verdict=PERFORMANCE_VERDICT_CANDIDATE,
        blocked_reasons=[],
        required_next_gates=[],
        review_safety_metadata=safe_perf_meta,
    )
    synthetic_exec = replace(
        chain[6],
        adapter_mode=ADAPTER_MODE_LIVE_DISABLED,
        blocked_reasons=[],
        required_next_gates=[],
        order_submitted=False,
        broker_call_performed=False,
        exchange_call_performed=False,
        paper_execution_allowed=False,
        live_execution_allowed=False,
        adapter_safety_metadata=safe_exec_meta,
    )
    synthetic_micro = replace(
        chain[7],
        micro_live_verdict=MICRO_LIVE_VERDICT_REVIEW_READY,
        blocked_reasons=[],
        required_next_gates=[],
        micro_live_execution_allowed=False,
        live_execution_allowed=False,
        gate_safety_metadata=safe_micro_meta,
    )

    bundle = build_readiness_bundle(
        decision_preview=replace(chain[1], blocked_reasons=[]),
        decision_risk=replace(chain[2], blocked_reasons=[]),
        paper_order_preview=replace(chain[3], blocked_reasons=[]),
        paper_fill_result=synthetic_fill,
        paper_performance_result=synthetic_perf,
        execution_adapter_result=synthetic_exec,
        micro_live_gate_result=synthetic_micro,
    )
    assert bundle.final_readiness_verdict == READINESS_VERDICT_MICRO_LIVE_REVIEW_READY
    assert bundle.micro_live_execution_allowed is False
    assert bundle.live_execution_allowed is False
    assert bundle.order_submitted is False
    assert bundle.broker_call_performed is False
    assert bundle.exchange_call_performed is False


def test_blocked_reasons_are_aggregated() -> None:
    bundle = _bundle_from_chain(_build_wallet_chain())
    assert bundle.blocked_reasons
    assert any("kill switch" in reason.lower() for reason in bundle.blocked_reasons)


def test_required_next_gates_are_aggregated() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    assert bundle.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in bundle.required_next_gates)


def test_stage_verdicts_are_included() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    assert bundle.stage_verdicts["decision_preview"]
    assert bundle.stage_verdicts["risk_gate"]
    assert bundle.stage_verdicts["paper_order_preview"]
    assert bundle.stage_verdicts["paper_fill_simulation"]
    assert bundle.stage_verdicts["paper_performance_gate"]
    assert bundle.stage_verdicts["execution_adapter"]
    assert bundle.stage_verdicts["micro_live_gate"]


def test_non_authorization_notice_is_included() -> None:
    bundle = _bundle_from_chain(_build_wallet_chain())
    lowered = bundle.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_safety_metadata_has_all_execution_flags_false() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    safety = bundle.readiness_safety_metadata
    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["readiness_bundle_only"] is True
    assert safety["live_submit_command_available"] is False


def test_output_contains_no_broker_exchange_credential_fields() -> None:
    bundle = _bundle_from_chain(_build_derivatives_chain())
    payload_text = json.dumps(asdict(bundle), sort_keys=True).lower()
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
    chain = _build_derivatives_chain()
    first = _bundle_from_chain(chain)
    second = _bundle_from_chain(chain)
    assert first == second


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_chain = _build_wallet_chain()
    derivatives_chain = _build_derivatives_chain()
    wallet_bundle = _bundle_from_chain(wallet_chain)
    derivatives_bundle = _bundle_from_chain(derivatives_chain)

    assert pipeline_allows_order(wallet_chain[0]) is False
    assert pipeline_allows_order(derivatives_chain[0]) is False
    assert wallet_bundle.micro_live_execution_allowed is False
    assert wallet_bundle.live_execution_allowed is False
    assert derivatives_bundle.micro_live_execution_allowed is False
    assert derivatives_bundle.live_execution_allowed is False
