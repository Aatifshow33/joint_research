from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.paper_fill_simulator import (
    FILL_STATUS_BLOCKED,
    FILL_STATUS_REJECTED,
    PaperFillMarketSnapshot,
    simulate_paper_fill,
)
from joint_research.signalcourt.paper_order_preview import (
    PaperOrderRequest,
    build_paper_order_preview,
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
    decision_preview = build_decision_preview(pipeline, run_id="wallet_fill_preview")
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
    return pipeline, paper_preview


def _build_derivatives_inputs():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_fill_preview")
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
    return pipeline, paper_preview


def test_wallet_flow_blocked_preview_produces_paper_fill_blocked() -> None:
    _, preview = _build_wallet_inputs()
    result = simulate_paper_fill(preview)

    assert result.simulated_fill_status == FILL_STATUS_BLOCKED
    assert result.paper_fill_allowed is False
    assert result.live_fill_allowed is False


def test_derivatives_watch_only_preview_produces_non_executable_fill() -> None:
    _, preview = _build_derivatives_inputs()
    result = simulate_paper_fill(preview)

    assert result.simulated_fill_status in {FILL_STATUS_BLOCKED, FILL_STATUS_REJECTED}
    assert result.paper_fill_allowed is False
    assert result.live_fill_allowed is False


def test_paper_fill_allowed_false_when_paper_order_allowed_false() -> None:
    _, preview = _build_wallet_inputs()
    result = simulate_paper_fill(preview)
    assert preview.paper_order_allowed is False
    assert result.paper_fill_allowed is False


def test_live_fill_allowed_is_always_false() -> None:
    _, preview = _build_derivatives_inputs()
    forced_preview = replace(preview, paper_order_allowed=True, live_order_allowed=True)
    result = simulate_paper_fill(
        forced_preview,
        market_snapshot=PaperFillMarketSnapshot(mark_price=100.0, fee_bps=5.0),
    )
    assert result.live_fill_allowed is False


def test_simulator_includes_blocked_reasons_and_required_next_gates() -> None:
    _, preview = _build_derivatives_inputs()
    result = simulate_paper_fill(preview)

    assert result.blocked_reasons
    assert result.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in result.required_next_gates)
    assert any("golden evaluations" in gate.lower() for gate in result.required_next_gates)


def test_simulator_includes_non_authorization_notice() -> None:
    _, preview = _build_wallet_inputs()
    result = simulate_paper_fill(preview)
    lowered = result.non_authorization_notice.lower()

    assert result.non_authorization_notice
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_simulator_safety_metadata_has_all_execution_flags_false() -> None:
    _, preview = _build_derivatives_inputs()
    result = simulate_paper_fill(preview)
    safety = result.simulator_safety_metadata

    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifact_written"] is False
    assert safety["ingestion_run"] is False
    assert safety["simulation_only"] is True


def test_simulator_output_contains_no_broker_exchange_or_live_order_payloads() -> None:
    _, preview = _build_derivatives_inputs()
    result = simulate_paper_fill(preview)
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


def test_simulator_is_deterministic() -> None:
    _, preview = _build_derivatives_inputs()
    snapshot = PaperFillMarketSnapshot(
        mark_price=125.0,
        bid_price=124.5,
        ask_price=125.5,
        slippage_bps=3.0,
        fee_bps=5.0,
        fill_mode="SIMULATED_MID",
    )
    first = simulate_paper_fill(preview, market_snapshot=snapshot)
    second = simulate_paper_fill(preview, market_snapshot=snapshot)
    assert first == second


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_preview = _build_wallet_inputs()
    derivatives_pipeline, derivatives_preview = _build_derivatives_inputs()

    wallet_fill = simulate_paper_fill(wallet_preview)
    derivatives_fill = simulate_paper_fill(derivatives_preview)

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_fill.paper_fill_allowed is False
    assert wallet_fill.live_fill_allowed is False
    assert derivatives_fill.paper_fill_allowed is False
    assert derivatives_fill.live_fill_allowed is False
