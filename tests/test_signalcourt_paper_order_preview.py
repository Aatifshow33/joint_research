from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import (
    ACTION_NO_TRADE,
    ACTION_WATCH_ONLY,
    build_decision_preview,
)
from joint_research.signalcourt.paper_order_preview import (
    PAPER_ORDER_ACTION_BLOCKED,
    PAPER_ORDER_ACTION_NO_TRADE,
    PAPER_ORDER_ACTION_WATCH_ONLY,
    PaperOrderRequest,
    SignalCourtPaperOrderPreview,
    build_paper_order_preview,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import (
    RISK_VERDICT_BLOCKED,
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
    preview = build_decision_preview(pipeline, run_id="wallet_decision_preview")
    risk_result = evaluate_decision_preview_risk_gate(preview)
    return pipeline, preview, risk_result


def _build_derivatives_inputs():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    preview = build_decision_preview(pipeline, run_id="derivatives_decision_preview")
    risk_result = evaluate_decision_preview_risk_gate(preview)
    return pipeline, preview, risk_result


def test_wallet_flow_blocked_no_trade_maps_to_non_executable_preview() -> None:
    _, decision_preview, risk_result = _build_wallet_inputs()
    request = PaperOrderRequest(symbol="BTCUSD", side="BUY", quantity=0.01, notional_usd=1.0)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
        order_request=request,
    )

    assert decision_preview.decision_action == ACTION_NO_TRADE
    assert paper_preview.paper_order_action in {
        PAPER_ORDER_ACTION_NO_TRADE,
        PAPER_ORDER_ACTION_BLOCKED,
    }
    assert paper_preview.paper_order_allowed is False
    assert paper_preview.live_order_allowed is False
    assert paper_preview.symbol == "BTCUSD"


def test_derivatives_watch_only_maps_to_non_executable_preview() -> None:
    _, decision_preview, risk_result = _build_derivatives_inputs()
    request = PaperOrderRequest(symbol="ETHUSD", side="BUY", quantity=0.02, notional_usd=2.0)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
        order_request=request,
    )

    assert decision_preview.decision_action == ACTION_WATCH_ONLY
    assert paper_preview.paper_order_action in {
        PAPER_ORDER_ACTION_WATCH_ONLY,
        PAPER_ORDER_ACTION_BLOCKED,
    }
    assert paper_preview.paper_order_allowed is False
    assert paper_preview.live_order_allowed is False
    assert paper_preview.symbol == "ETHUSD"


def test_paper_order_allowed_is_false_when_risk_gate_blocks_paper() -> None:
    _, decision_preview, risk_result = _build_wallet_inputs()
    forced_blocked_risk = replace(
        risk_result,
        paper_allowed=False,
        risk_verdict=RISK_VERDICT_BLOCKED,
    )

    paper_preview = build_paper_order_preview(decision_preview, forced_blocked_risk)
    assert paper_preview.paper_order_allowed is False


def test_live_order_allowed_is_always_false_in_this_phase() -> None:
    _, decision_preview, risk_result = _build_derivatives_inputs()
    forced_live_allowed_risk = replace(
        risk_result,
        paper_allowed=True,
        live_allowed=True,
        risk_verdict="PAPER_ALLOWED",
        blocked_reasons=[],
        required_next_gates=[],
    )

    paper_preview = build_paper_order_preview(decision_preview, forced_live_allowed_risk)
    assert paper_preview.live_order_allowed is False
    assert paper_preview.paper_order_allowed is False


def test_preview_includes_blocked_reasons_and_required_next_gates() -> None:
    _, decision_preview, risk_result = _build_derivatives_inputs()
    paper_preview = build_paper_order_preview(decision_preview, risk_result)

    assert paper_preview.blocked_reasons
    assert paper_preview.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in paper_preview.required_next_gates)
    assert any("golden evaluations" in gate.lower() for gate in paper_preview.required_next_gates)


def test_preview_includes_non_authorization_notice() -> None:
    _, decision_preview, risk_result = _build_wallet_inputs()
    paper_preview = build_paper_order_preview(decision_preview, risk_result)

    assert paper_preview.non_authorization_notice
    lowered = paper_preview.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_preview_output_contains_no_order_placement_payload_fields() -> None:
    _, decision_preview, risk_result = _build_derivatives_inputs()
    paper_preview = build_paper_order_preview(decision_preview, risk_result)
    payload_text = json.dumps(asdict(paper_preview), sort_keys=True).lower()

    forbidden_terms = [
        "broker_api",
        "exchange_api",
        "order_placement_payload",
        "live_execution_payload",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in payload_text


def test_preview_is_deterministic() -> None:
    _, decision_preview, risk_result = _build_derivatives_inputs()
    request = PaperOrderRequest(
        symbol="ETHUSD",
        side="BUY",
        quantity=0.1,
        limit_price=100.0,
        notional_usd=10.0,
        venue="paper_local",
        order_type="limit",
    )

    first = build_paper_order_preview(decision_preview, risk_result, order_request=request)
    second = build_paper_order_preview(decision_preview, risk_result, order_request=request)
    assert first == second
    assert isinstance(first, SignalCourtPaperOrderPreview)


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_decision_preview, wallet_risk = _build_wallet_inputs()
    derivatives_pipeline, derivatives_decision_preview, derivatives_risk = _build_derivatives_inputs()

    wallet_paper_preview = build_paper_order_preview(wallet_decision_preview, wallet_risk)
    derivatives_paper_preview = build_paper_order_preview(derivatives_decision_preview, derivatives_risk)

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_paper_preview.paper_order_allowed is False
    assert wallet_paper_preview.live_order_allowed is False
    assert derivatives_paper_preview.paper_order_allowed is False
    assert derivatives_paper_preview.live_order_allowed is False
