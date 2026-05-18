from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from joint_research.signalcourt.decision_preview import build_decision_preview
from joint_research.signalcourt.paper_order_preview import (
    PAPER_ORDER_ACTION_BLOCKED,
    PAPER_ORDER_ACTION_NO_TRADE,
    PAPER_ORDER_ACTION_WATCH_ONLY,
    PaperOrderRequest,
    build_paper_order_preview,
)
from joint_research.signalcourt.paper_trade_ledger import write_paper_trade_ledger_record
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


def _build_wallet_preview():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="wallet_preview")
    risk_result = evaluate_decision_preview_risk_gate(decision_preview)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
        order_request=PaperOrderRequest(
            symbol="BTCUSD",
            side="BUY",
            quantity=0.01,
            notional_usd=1.0,
            venue="paper_local",
            order_type="limit",
        ),
    )
    return pipeline, paper_preview


def _build_derivatives_preview():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    decision_preview = build_decision_preview(pipeline, run_id="derivatives_preview")
    risk_result = evaluate_decision_preview_risk_gate(decision_preview)
    paper_preview = build_paper_order_preview(
        decision_preview,
        risk_result,
        order_request=PaperOrderRequest(
            symbol="ETHUSD",
            side="BUY",
            quantity=0.02,
            notional_usd=2.0,
            venue="paper_local",
            order_type="limit",
        ),
    )
    return pipeline, paper_preview


def test_ledger_requires_explicit_ledger_dir() -> None:
    _, preview = _build_wallet_preview()
    with pytest.raises(ValueError, match="ledger_dir"):
        write_paper_trade_ledger_record(preview, None)


def test_ledger_writes_only_under_explicit_tmp_path_directory(tmp_path: Path) -> None:
    _, preview = _build_wallet_preview()
    ledger_dir = tmp_path / "ledger"
    result = write_paper_trade_ledger_record(preview, ledger_dir, session_id="session_1")

    assert result.ledger_path.parent == ledger_dir.resolve()
    result.ledger_path.relative_to(tmp_path.resolve())
    assert result.ledger_path.name == "signalcourt_paper_trade_ledger_session_1.jsonl"


def test_ledger_appends_multiple_records_without_overwriting(tmp_path: Path) -> None:
    _, preview = _build_wallet_preview()
    ledger_dir = tmp_path / "append"

    first = write_paper_trade_ledger_record(preview, ledger_dir, session_id="append_test")
    second = write_paper_trade_ledger_record(preview, ledger_dir, session_id="append_test")

    assert first.ledger_path == second.ledger_path
    lines = first.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == json.loads(lines[1])


def test_each_ledger_line_is_valid_one_line_json(tmp_path: Path) -> None:
    _, preview = _build_derivatives_preview()
    result = write_paper_trade_ledger_record(preview, tmp_path / "json_lines", session_id="json_lines")

    raw = result.ledger_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    lines = raw.splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert isinstance(parsed, dict)


def test_ledger_preserves_blocked_lane_non_executing_flags(tmp_path: Path) -> None:
    _, wallet_preview = _build_wallet_preview()
    _, derivatives_preview = _build_derivatives_preview()
    path = tmp_path / "blocked_flags"

    wallet_result = write_paper_trade_ledger_record(wallet_preview, path, session_id="blocked")
    write_paper_trade_ledger_record(derivatives_preview, path, session_id="blocked")

    lines = wallet_result.ledger_path.read_text(encoding="utf-8").splitlines()
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["paper_order_action"] in {
        PAPER_ORDER_ACTION_NO_TRADE,
        PAPER_ORDER_ACTION_BLOCKED,
    }
    assert payloads[1]["paper_order_action"] in {
        PAPER_ORDER_ACTION_WATCH_ONLY,
        PAPER_ORDER_ACTION_BLOCKED,
    }
    for payload in payloads:
        assert payload["paper_order_allowed"] is False
        assert payload["live_order_allowed"] is False


def test_ledger_includes_non_authorization_notice(tmp_path: Path) -> None:
    _, preview = _build_wallet_preview()
    result = write_paper_trade_ledger_record(preview, tmp_path / "notice", session_id="notice")
    payload = json.loads(result.ledger_path.read_text(encoding="utf-8").splitlines()[0])

    assert payload["non_authorization_notice"]
    lowered = payload["non_authorization_notice"].lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_ledger_includes_writer_safety_metadata_with_all_execution_flags_false(
    tmp_path: Path,
) -> None:
    _, preview = _build_derivatives_preview()
    result = write_paper_trade_ledger_record(preview, tmp_path / "safety", session_id="safety")
    payload = json.loads(result.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    safety = payload["writer_safety_metadata"]

    assert safety["execution_performed"] is False
    assert safety["broker_call_performed"] is False
    assert safety["exchange_call_performed"] is False
    assert safety["live_order_submitted"] is False
    assert safety["paper_order_submitted"] is False
    assert safety["artifacts_refreshed"] is False
    assert safety["ingestion_run"] is False
    assert safety["explicit_ledger_dir_only"] is True


@pytest.mark.parametrize("unsafe_session_id", ["../escape", "..", "bad/path", "bad\\path", "", "."])
def test_ledger_rejects_unsafe_or_traversal_session_ids(
    tmp_path: Path,
    unsafe_session_id: str,
) -> None:
    _, preview = _build_wallet_preview()
    with pytest.raises(ValueError, match="session_id"):
        write_paper_trade_ledger_record(preview, tmp_path / "unsafe_session", session_id=unsafe_session_id)


def test_ledger_rejects_unsafe_or_traversal_run_id(tmp_path: Path) -> None:
    _, preview = _build_wallet_preview()
    unsafe_preview = replace(preview, run_id="../unsafe")
    with pytest.raises(ValueError, match="run_id"):
        write_paper_trade_ledger_record(unsafe_preview, tmp_path / "unsafe_run", session_id="safe_session")


def test_ledger_output_has_no_broker_exchange_or_execution_payload_terms(tmp_path: Path) -> None:
    _, preview = _build_derivatives_preview()
    result = write_paper_trade_ledger_record(preview, tmp_path / "payload_terms", session_id="payload_terms")
    payload_text = result.ledger_path.read_text(encoding="utf-8").lower()

    forbidden_terms = [
        "broker_api",
        "exchange_api",
        "submit_live_order",
        "place_live_order",
        "paper_order_execution_payload",
        "live_execution_payload",
    ]
    for term in forbidden_terms:
        assert term not in payload_text


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline, wallet_preview = _build_wallet_preview()
    derivatives_pipeline, derivatives_preview = _build_derivatives_preview()

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_preview.paper_order_allowed is False
    assert wallet_preview.live_order_allowed is False
    assert derivatives_preview.paper_order_allowed is False
    assert derivatives_preview.live_order_allowed is False
