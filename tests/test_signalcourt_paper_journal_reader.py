from __future__ import annotations

from pathlib import Path

import pytest

from joint_research.signalcourt.paper_journal_reader import read_paper_journal_records
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


def test_reader_requires_explicit_file_or_directory_input() -> None:
    with pytest.raises(ValueError, match="Explicit input required"):
        read_paper_journal_records()
    with pytest.raises(ValueError, match="Provide only one input"):
        read_paper_journal_records(
            jsonl_file_path=Path("x.jsonl"),
            output_dir_path=Path("y"),
        )


def test_reader_reads_valid_jsonl_and_returns_summary_fields(tmp_path: Path) -> None:
    wallet_pipeline, wallet_trace = _build_wallet_pipeline_and_trace()
    derivatives_pipeline, derivatives_trace = _build_derivatives_pipeline_and_trace()
    out_dir = tmp_path / "reader_input"

    _ = write_paper_journal_entry(
        wallet_pipeline.journal_entry,
        wallet_trace,
        out_dir,
        run_id="run_wallet",
    )
    _ = write_paper_journal_entry(
        derivatives_pipeline.journal_entry,
        derivatives_trace,
        out_dir,
        run_id="run_derivatives",
    )

    summary = read_paper_journal_records(output_dir_path=out_dir)
    assert summary.record_count == 2
    assert summary.run_ids == ["run_derivatives", "run_wallet"]
    assert summary.lanes_encountered == ["derivatives_regime", "wallet_flow_signal"]
    assert set(summary.final_statuses_encountered).issubset(
        {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}
    )
    assert summary.blocked_count == 2
    assert summary.no_trade_count >= 1
    assert summary.malformed_jsonl_line_warnings == []
    assert summary.missing_safety_field_warnings == []
    assert summary.containment_path_safety_warnings == []
    assert summary.non_authorization_notice


def test_reader_reports_malformed_jsonl_line_warnings(tmp_path: Path) -> None:
    broken = tmp_path / "broken.jsonl"
    broken.write_text(
        '{"run_id":"ok","lane":"wallet_flow_signal","final_status":"NO_TRADE_BLOCKED","blocked":true,"paper_order_allowed":false,"live_order_allowed":false,"non_authorization_notice":"x"}\n'
        + '{"bad_json":\n',
        encoding="utf-8",
    )

    summary = read_paper_journal_records(jsonl_file_path=broken)
    assert summary.record_count == 1
    assert len(summary.malformed_jsonl_line_warnings) == 1
    assert "malformed JSONL line" in summary.malformed_jsonl_line_warnings[0]


def test_reader_reports_missing_safety_field_warnings(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    missing.write_text(
        '{"run_id":"r1","lane":"wallet_flow_signal","final_status":"NO_TRADE_BLOCKED","blocked":true}\n',
        encoding="utf-8",
    )

    summary = read_paper_journal_records(jsonl_file_path=missing)
    assert summary.record_count == 1
    assert summary.blocked_count == 1
    assert summary.no_trade_count == 1
    assert len(summary.missing_safety_field_warnings) >= 1
    assert any("missing safety field" in warning for warning in summary.missing_safety_field_warnings)


def test_reader_does_not_mutate_source_jsonl_contents(tmp_path: Path) -> None:
    wallet_pipeline, wallet_trace = _build_wallet_pipeline_and_trace()
    out_dir = tmp_path / "immutable"
    result = write_paper_journal_entry(
        wallet_pipeline.journal_entry,
        wallet_trace,
        out_dir,
        run_id="immutable_run",
    )
    before = result.output_path.read_bytes()
    _ = read_paper_journal_records(jsonl_file_path=result.output_path)
    after = result.output_path.read_bytes()
    assert before == after


def test_reader_reads_only_from_explicit_tmp_inputs(tmp_path: Path) -> None:
    explicit_dir = tmp_path / "explicit"
    outside_dir = tmp_path / "outside"
    explicit_dir.mkdir(parents=True, exist_ok=True)
    outside_dir.mkdir(parents=True, exist_ok=True)

    explicit_file = explicit_dir / "a.jsonl"
    explicit_file.write_text(
        '{"run_id":"explicit","lane":"wallet_flow_signal","final_status":"NO_TRADE_BLOCKED","blocked":true,"paper_order_allowed":false,"live_order_allowed":false,"non_authorization_notice":"x"}\n',
        encoding="utf-8",
    )
    outside_file = outside_dir / "b.jsonl"
    outside_file.write_text(
        '{"run_id":"outside","lane":"wallet_flow_signal","final_status":"NO_TRADE_BLOCKED","blocked":true,"paper_order_allowed":false,"live_order_allowed":false,"non_authorization_notice":"x"}\n',
        encoding="utf-8",
    )

    summary = read_paper_journal_records(output_dir_path=explicit_dir)
    assert summary.record_count == 1
    assert summary.run_ids == ["explicit"]
    assert summary.source_files == [str(explicit_file.resolve())]
    assert str(outside_file.resolve()) not in summary.source_files


def test_reader_does_not_authorize_paper_or_live_trading(tmp_path: Path) -> None:
    wallet_pipeline, wallet_trace = _build_wallet_pipeline_and_trace()
    out_dir = tmp_path / "auth_guard"
    _ = write_paper_journal_entry(
        wallet_pipeline.journal_entry,
        wallet_trace,
        out_dir,
        run_id="auth_guard",
    )

    summary = read_paper_journal_records(output_dir_path=out_dir)
    assert summary.record_count == 1
    assert summary.blocked_count == 1
    assert summary.no_trade_count == 1
    assert summary.non_authorization_notice
    assert "does not authorize" in summary.non_authorization_notice.lower()


@pytest.mark.parametrize(
    "unsafe_path",
    ["../bad.jsonl", "..", "", "bad:name.jsonl"],
)
def test_reader_rejects_unsafe_or_traversal_input_paths(unsafe_path: str) -> None:
    with pytest.raises(ValueError, match="Unsafe path|Input path cannot be empty"):
        read_paper_journal_records(jsonl_file_path=unsafe_path)
