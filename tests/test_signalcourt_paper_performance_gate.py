from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.paper_fill_simulator import simulate_paper_fill
from joint_research.signalcourt.paper_order_preview import (
    PaperOrderRequest,
    build_paper_order_preview,
)
from joint_research.signalcourt.paper_performance_gate import (
    PERFORMANCE_VERDICT_BLOCKED,
    PERFORMANCE_VERDICT_LIVE_REVIEW_BLOCKED,
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


def _build_wallet_fill():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="wallet_performance_review")
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
    return pipeline, fill


def _build_derivatives_fill():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_performance_review")
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
    return pipeline, fill


def test_empty_input_returns_performance_blocked() -> None:
    result = review_paper_performance([])
    assert result.performance_verdict == PERFORMANCE_VERDICT_BLOCKED
    assert result.paper_review_allowed is False
    assert result.live_review_allowed is False


def test_wallet_flow_blocked_fills_remain_review_blocked() -> None:
    _, fill = _build_wallet_fill()
    result = review_paper_performance([fill])
    assert result.performance_verdict == PERFORMANCE_VERDICT_BLOCKED
    assert result.paper_review_allowed is False
    assert result.live_review_allowed is False


def test_derivatives_watch_only_fills_remain_non_executable() -> None:
    _, fill = _build_derivatives_fill()
    result = review_paper_performance([fill])
    assert result.performance_verdict in {PERFORMANCE_VERDICT_BLOCKED, PERFORMANCE_VERDICT_REVIEW_ONLY}
    assert result.paper_review_allowed is False
    assert result.live_review_allowed is False


def test_live_review_allowed_is_always_false() -> None:
    _, fill = _build_derivatives_fill()
    forced = replace(fill, live_fill_allowed=True)
    result = review_paper_performance([forced])
    assert result.live_review_allowed is False


def test_review_blocks_if_any_fill_has_live_fill_allowed_true() -> None:
    _, fill = _build_derivatives_fill()
    forced = replace(fill, live_fill_allowed=True)
    result = review_paper_performance([fill, forced])
    assert result.performance_verdict == PERFORMANCE_VERDICT_LIVE_REVIEW_BLOCKED
    assert any("live-fill-allowed" in reason for reason in result.blocked_reasons)


def test_review_blocks_if_execution_like_safety_flags_are_present() -> None:
    _, fill = _build_wallet_fill()
    mutated_meta = dict(fill.simulator_safety_metadata)
    mutated_meta["execution_performed"] = True
    forced = replace(fill, simulator_safety_metadata=mutated_meta)
    result = review_paper_performance([forced])
    assert result.performance_verdict == PERFORMANCE_VERDICT_BLOCKED
    assert any("execution-like safety metadata" in reason for reason in result.blocked_reasons)


def test_review_includes_blocked_reasons_and_required_next_gates() -> None:
    _, fill = _build_derivatives_fill()
    result = review_paper_performance([fill])
    assert result.blocked_reasons
    assert result.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in result.required_next_gates)
    assert any("golden evaluations" in gate.lower() for gate in result.required_next_gates)


def test_review_includes_non_authorization_notice() -> None:
    _, fill = _build_wallet_fill()
    result = review_paper_performance([fill])
    lowered = result.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_review_safety_metadata_has_all_execution_flags_false() -> None:
    _, fill = _build_derivatives_fill()
    result = review_paper_performance([fill])
    safety = result.review_safety_metadata
    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["review_only"] is True


def test_review_output_contains_no_broker_exchange_live_order_payloads() -> None:
    _, fill = _build_derivatives_fill()
    result = review_paper_performance([fill])
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


def test_review_is_deterministic() -> None:
    _, fill = _build_derivatives_fill()
    first = review_paper_performance([fill], run_id="deterministic_review")
    second = review_paper_performance([fill], run_id="deterministic_review")
    assert first == second


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_fill = _build_wallet_fill()
    derivatives_pipeline, derivatives_fill = _build_derivatives_fill()
    wallet_result = review_paper_performance([wallet_fill])
    derivatives_result = review_paper_performance([derivatives_fill])

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_result.paper_review_allowed is False
    assert wallet_result.live_review_allowed is False
    assert derivatives_result.paper_review_allowed is False
    assert derivatives_result.live_review_allowed is False
