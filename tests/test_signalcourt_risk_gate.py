from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from joint_research.signalcourt.decision_preview import (
    ACTION_NO_TRADE,
    ACTION_WATCH_ONLY,
    build_decision_preview,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import (
    DecisionPreviewRiskPolicy,
    RISK_VERDICT_BLOCKED,
    RISK_VERDICT_LIVE_BLOCKED,
    RISK_VERDICT_PAPER_REVIEW_ONLY,
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


def _build_wallet_preview():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    return build_decision_preview(pipeline, run_id="wallet_preview")


def _build_derivatives_preview():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    return build_decision_preview(pipeline, run_id="derivatives_preview")


def test_wallet_flow_blocked_no_trade_preview_returns_risk_blocked() -> None:
    preview = _build_wallet_preview()
    result = evaluate_decision_preview_risk_gate(preview)

    assert preview.decision_action == ACTION_NO_TRADE
    assert result.risk_verdict == RISK_VERDICT_BLOCKED
    assert result.paper_allowed is False
    assert result.live_allowed is False


def test_derivatives_watch_only_preview_remains_not_paper_or_live_allowed() -> None:
    preview = _build_derivatives_preview()
    result = evaluate_decision_preview_risk_gate(preview)

    assert preview.decision_action == ACTION_WATCH_ONLY
    assert result.risk_verdict in {RISK_VERDICT_BLOCKED, RISK_VERDICT_PAPER_REVIEW_ONLY}
    assert result.paper_allowed is False
    assert result.live_allowed is False


def test_kill_switch_blocks_paper_and_live() -> None:
    preview = _build_wallet_preview()
    policy = DecisionPreviewRiskPolicy(
        max_notional_usd=50.0,
        max_position_notional_usd=10.0,
        max_daily_loss_usd=2.0,
        max_session_loss_usd=1.0,
        allowlisted_lanes=("wallet_flow_signal",),
        allowlisted_symbols=(),
        allowlisted_venues=(),
        paper_trading_enabled=True,
        live_trading_enabled=True,
        kill_switch_enabled=True,
        require_manual_approval=False,
        allow_market_orders=False,
        allow_leverage=False,
    )
    result = evaluate_decision_preview_risk_gate(preview, risk_policy=policy)

    assert result.paper_allowed is False
    assert result.live_allowed is False
    assert any("kill switch" in reason.lower() for reason in result.blocked_reasons)


def test_paper_trading_disabled_blocks_paper() -> None:
    preview = _build_derivatives_preview()
    policy = DecisionPreviewRiskPolicy(
        max_notional_usd=50.0,
        max_position_notional_usd=10.0,
        max_daily_loss_usd=2.0,
        max_session_loss_usd=1.0,
        allowlisted_lanes=("derivatives_regime",),
        allowlisted_symbols=(),
        allowlisted_venues=(),
        paper_trading_enabled=False,
        live_trading_enabled=True,
        kill_switch_enabled=False,
        require_manual_approval=False,
        allow_market_orders=False,
        allow_leverage=False,
    )
    result = evaluate_decision_preview_risk_gate(preview, risk_policy=policy)

    assert result.paper_allowed is False
    assert any("paper trading is disabled" in reason.lower() for reason in result.blocked_reasons)


def test_live_trading_disabled_blocks_live() -> None:
    preview = _build_derivatives_preview()
    policy = DecisionPreviewRiskPolicy(
        max_notional_usd=50.0,
        max_position_notional_usd=10.0,
        max_daily_loss_usd=2.0,
        max_session_loss_usd=1.0,
        allowlisted_lanes=("derivatives_regime",),
        allowlisted_symbols=(),
        allowlisted_venues=(),
        paper_trading_enabled=True,
        live_trading_enabled=False,
        kill_switch_enabled=False,
        require_manual_approval=False,
        allow_market_orders=False,
        allow_leverage=False,
    )
    result = evaluate_decision_preview_risk_gate(preview, risk_policy=policy)

    assert result.live_allowed is False
    assert any("live trading is disabled" in reason.lower() for reason in result.blocked_reasons)


def test_live_allowed_is_always_false_in_this_phase() -> None:
    preview = replace(_build_derivatives_preview(), live_eligible=True)
    policy = DecisionPreviewRiskPolicy(
        max_notional_usd=50.0,
        max_position_notional_usd=10.0,
        max_daily_loss_usd=2.0,
        max_session_loss_usd=1.0,
        allowlisted_lanes=("derivatives_regime",),
        allowlisted_symbols=(),
        allowlisted_venues=(),
        paper_trading_enabled=True,
        live_trading_enabled=True,
        kill_switch_enabled=False,
        require_manual_approval=False,
        allow_market_orders=True,
        allow_leverage=False,
    )
    result = evaluate_decision_preview_risk_gate(preview, risk_policy=policy)

    assert result.risk_verdict == RISK_VERDICT_LIVE_BLOCKED
    assert result.live_allowed is False


def test_risk_gate_includes_blocked_reasons_and_required_next_gates() -> None:
    preview = _build_wallet_preview()
    result = evaluate_decision_preview_risk_gate(preview)

    assert result.blocked_reasons
    assert result.required_next_gates
    assert any("resolve blocker:" in gate.lower() for gate in result.required_next_gates)
    assert any("golden evaluations" in gate.lower() for gate in result.required_next_gates)


def test_risk_gate_includes_non_authorization_notice() -> None:
    preview = _build_wallet_preview()
    result = evaluate_decision_preview_risk_gate(preview)
    lowered = result.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_risk_gate_output_has_no_order_or_broker_exchange_payload_terms() -> None:
    preview = _build_derivatives_preview()
    result = evaluate_decision_preview_risk_gate(preview)
    payload_text = json.dumps(asdict(result), sort_keys=True).lower()
    forbidden_terms = [
        "place_order",
        "submit_order",
        "order_placement",
        "broker_api",
        "exchange_api",
    ]
    for term in forbidden_terms:
        assert term not in payload_text


def test_decision_preview_golden_blocked_no_execution_behavior_unchanged() -> None:
    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    wallet_preview = build_decision_preview(wallet_pipeline)
    derivatives_preview = build_decision_preview(derivatives_pipeline)
    wallet_risk = evaluate_decision_preview_risk_gate(wallet_preview)
    derivatives_risk = evaluate_decision_preview_risk_gate(derivatives_preview)

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_risk.paper_allowed is False
    assert wallet_risk.live_allowed is False
    assert derivatives_risk.paper_allowed is False
    assert derivatives_risk.live_allowed is False
