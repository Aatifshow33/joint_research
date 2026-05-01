from __future__ import annotations

from pathlib import Path

from joint_research.ops.collection_snapshot import (
    SnapshotMetrics,
    SnapshotStep,
    classify_status,
    load_wallet_flow_top_rejection_reasons,
    parse_metrics,
    parse_steps,
    write_summary,
)


def test_status_classification() -> None:
    assert classify_status(simulation_ready=0, paper_ready=1, any_failures=False) == "PAPER_TRACKING_READY"
    assert classify_status(simulation_ready=1, paper_ready=0, any_failures=False) == "MORE_DATA_NEEDED"
    assert classify_status(simulation_ready=0, paper_ready=0, any_failures=False) == "MORE_DATA_NEEDED"
    assert classify_status(simulation_ready=0, paper_ready=0, any_failures=True) == "NOT_TRADEABLE"


def test_parse_command_outputs_for_metrics() -> None:
    log_text = """
>>> STEP_START backfill
>>> COMMAND joint-research ingest wallet-flow-backfill-plan --stage stage_1_quick --execute
EXPLORATORY ONLY - NOT TRADEABLE
coverage_before wallet_flow_rows=1001 trade_rows=992 copy_rows=9 market_flow_hourly_rows=397 whale_flow_hourly_rows=392
coverage_after wallet_flow_rows=2994 trade_rows=2972 copy_rows=22 market_flow_hourly_rows=1135 whale_flow_hourly_rows=1096
>>> EXIT_CODE 0
>>> STEP_END
>>> STEP_START research
>>> COMMAND joint-research research wallet-flow-signal
segment_rows=764 simulation_ready=0 watchlist=0 weak=0 rejected=764
>>> EXIT_CODE 0
>>> STEP_END
>>> STEP_START simulate
>>> COMMAND joint-research research simulate --candidate-source wallet-flow-signal
candidate_source=wallet-flow-signal candidates_simulated=0 trades=0 paper_pnl=$0.00 paper_ready=0 watchlist=0 rejected=0
>>> EXIT_CODE 0
>>> STEP_END
""".strip()
    steps = parse_steps(log_text)
    metrics = parse_metrics(steps)

    assert len(steps) == 3
    assert metrics.wallet_flow_rows_before == 1001
    assert metrics.wallet_flow_rows_after == 2994
    assert metrics.market_flow_rows_before == 397
    assert metrics.market_flow_rows_after == 1135
    assert metrics.whale_flow_rows_before == 392
    assert metrics.whale_flow_rows_after == 1096
    assert metrics.simulation_ready == 0
    assert metrics.paper_ready == 0


def test_artifact_writing(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.md"
    steps = [
        SnapshotStep(
            name="simulate",
            command="joint-research research simulate --candidate-source wallet-flow-signal",
            exit_code=0,
            output="paper_ready=0 simulation_ready=0 rows_written=0",
        )
    ]
    metrics = SnapshotMetrics(
        simulation_ready=0,
        paper_ready=0,
        wallet_flow_rows_before=10,
        wallet_flow_rows_after=20,
        market_flow_rows_before=5,
        market_flow_rows_after=8,
        whale_flow_rows_before=4,
        whale_flow_rows_after=7,
    )
    write_summary(
        summary_path=summary_path,
        steps=steps,
        warnings=["warning=demo"],
        metrics=metrics,
        status="MORE_DATA_NEEDED",
    )

    text = summary_path.read_text()
    assert "# Daily Research Snapshot" in text
    assert "status=MORE_DATA_NEEDED" in text
    assert "before_wallet_flow_rows=10" in text
    assert "after_wallet_flow_rows=20" in text
    assert "top_rejection_reasons=unknown" in text


def test_no_trade_safety_wording(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.md"
    write_summary(
        summary_path=summary_path,
        steps=[],
        warnings=[],
        metrics=SnapshotMetrics(
            simulation_ready=0,
            paper_ready=0,
            wallet_flow_rows_before=None,
            wallet_flow_rows_after=None,
            market_flow_rows_before=None,
            market_flow_rows_after=None,
            whale_flow_rows_before=None,
            whale_flow_rows_after=None,
        ),
        status="NOT_TRADEABLE",
    )
    text = summary_path.read_text()
    assert "No live execution." in text
    assert "No trades placed." in text
    assert "No API keys used." in text
    assert "NOT_TRADEABLE" in text


def test_load_wallet_flow_top_rejection_reasons(tmp_path: Path) -> None:
    diagnostics = tmp_path / "wallet_flow_rejection_diagnostics.csv"
    diagnostics.write_text(
        "\n".join(
            [
                "rejection_reasons",
                "insufficient_unique_flow_hours;low_sample_count",
                "low_sample_count;weak_win_rate",
                "low_sample_count",
                "",
            ]
        )
        + "\n"
    )
    reasons = load_wallet_flow_top_rejection_reasons(diagnostics, limit=3)
    assert reasons == [
        ("low_sample_count", 3),
        ("insufficient_unique_flow_hours", 1),
        ("weak_win_rate", 1),
    ]


def test_load_wallet_flow_top_rejection_reasons_missing_file() -> None:
    reasons = load_wallet_flow_top_rejection_reasons(
        Path("/tmp/does-not-exist-wallet-flow-diagnostics.csv"),
        limit=3,
    )
    assert reasons == []
