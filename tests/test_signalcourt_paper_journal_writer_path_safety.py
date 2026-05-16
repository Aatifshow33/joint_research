from __future__ import annotations

import json
from pathlib import Path

import pytest

from joint_research.signalcourt.paper_journal_writer import write_paper_journal_entry
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config
from joint_research.signalcourt.trace import build_trace_from_pipeline_result


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


def _build_wallet_pipeline_and_trace():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    trace = build_trace_from_pipeline_result(pipeline)
    return pipeline, trace


def _build_derivatives_pipeline_and_trace():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    trace = build_trace_from_pipeline_result(pipeline)
    return pipeline, trace


def test_writer_appends_deterministic_jsonl_records_without_overwrite(tmp_path: Path) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    output_dir = tmp_path / "append_only"

    result_one = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        output_dir,
        run_id="append_contract",
    )
    result_two = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        output_dir,
        run_id="append_contract",
    )

    assert result_one.output_path == result_two.output_path
    assert result_one.output_path.parent == output_dir.resolve()
    assert list(output_dir.glob("*.jsonl")) == [result_one.output_path]

    lines = result_one.output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    payload_first = json.loads(lines[0])
    payload_second = json.loads(lines[1])
    assert payload_first == payload_second

    for payload in (payload_first, payload_second):
        assert payload["blocked"] is True
        assert payload["paper_order_allowed"] is False
        assert payload["live_order_allowed"] is False
        assert payload["final_status"] == "NO_TRADE_BLOCKED"
        assert payload["non_authorization_notice"]

    file_text = result_one.output_path.read_text(encoding="utf-8")
    assert file_text.endswith("\n")


def test_writer_output_path_stays_within_provided_directory(tmp_path: Path) -> None:
    pipeline, trace = _build_derivatives_pipeline_and_trace()
    nested_output_dir = tmp_path / "a" / ".." / "b" / "c"

    result = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        nested_output_dir,
        run_id="path_safety",
    )
    resolved_dir = nested_output_dir.resolve()

    assert result.output_path.parent == resolved_dir
    result.output_path.relative_to(tmp_path.resolve())
    assert result.output_path.name == "signalcourt_paper_journal_path_safety.jsonl"
    payload = json.loads(result.output_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["paper_order_allowed"] is False
    assert payload["live_order_allowed"] is False


@pytest.mark.parametrize(
    "unsafe_run_id",
    ["../escape", "..", "nested/path", "bad\\path", "/abs", "bad:id", ""],
)
def test_writer_rejects_traversal_or_unsafe_identifiers(
    tmp_path: Path,
    unsafe_run_id: str,
) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    with pytest.raises(ValueError, match="run_id"):
        write_paper_journal_entry(
            pipeline.journal_entry,
            trace,
            tmp_path / "unsafe",
            run_id=unsafe_run_id,
        )


@pytest.mark.parametrize("lane_name", ["wallet", "derivatives"])
def test_writer_records_do_not_include_execution_or_broker_exchange_payloads(
    tmp_path: Path,
    lane_name: str,
) -> None:
    if lane_name == "wallet":
        pipeline, trace = _build_wallet_pipeline_and_trace()
    else:
        pipeline, trace = _build_derivatives_pipeline_and_trace()

    result = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        tmp_path / f"payload_{lane_name}",
        run_id=f"payload_{lane_name}",
    )

    payload_text = result.output_path.read_text(encoding="utf-8").lower()
    forbidden_terms = [
        "paper_enter",
        "paper_exit",
        "live_enter",
        "live_review_required",
        "place_order",
        "submit_order",
        "order_placement",
        "broker_api",
        "exchange_api",
    ]
    for term in forbidden_terms:
        assert term not in payload_text
