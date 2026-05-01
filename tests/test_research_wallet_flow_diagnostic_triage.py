from __future__ import annotations

from joint_research.research.wallet_flow_diagnostic_triage import (
    build_wallet_flow_diagnostic_triage,
    read_wallet_flow_rejection_diagnostics,
    render_wallet_flow_diagnostic_triage,
    write_wallet_flow_diagnostic_triage_report,
)
from joint_research.research.wallet_flow_signal import WalletFlowRejectionDiagnostic


def _diag(
    rank: int,
    *,
    market_id: str,
    reasons: str,
    grade: str = "REJECTED",
    retained: bool = True,
    horizon: int = 1,
    segment_type: str = "all",
    segment_value: str = "all",
    improvement: float = 0.0008,
    net_after_cost: float = 0.0001,
    win_rate: float = 0.55,
    stability: float = 0.55,
) -> WalletFlowRejectionDiagnostic:
    return WalletFlowRejectionDiagnostic(
        rank=rank,
        asset="BTC",
        market_id=market_id,
        market_slug=market_id,
        token_id=f"{market_id}-tok",
        horizon_hours=horizon,
        feature_name="net_flow_usdc",
        segment_type=segment_type,
        segment_value=segment_value,
        final_grade=grade,
        retained_after_dedup=retained,
        rejection_reasons=reasons,
        sample_count=72,
        test_samples=24,
        unique_flow_hours=45,
        active_wallet_coverage=0.68,
        non_zero_net_flow_coverage=0.69,
        test_improvement_over_baseline=improvement,
        net_test_improvement_after_cost=net_after_cost,
        test_win_rate=win_rate,
        stability=stability,
    )


def test_diagnostic_triage_generation_is_deterministic() -> None:
    diagnostics = [
        _diag(2, market_id="m2", reasons="weak_win_rate;low_sample_count"),
        _diag(1, market_id="m1", reasons="low_sample_count;duplicate_segment_competition"),
    ]

    first = build_wallet_flow_diagnostic_triage(diagnostics)
    second = build_wallet_flow_diagnostic_triage(diagnostics)

    assert first == second
    assert first.total_rejected == 2
    assert first.duplicate_segment_competition_count == 1


def test_reason_count_ordering_and_action_buckets() -> None:
    diagnostics = [
        _diag(1, market_id="m1", reasons="weak_win_rate;low_sample_count"),
        _diag(2, market_id="m2", reasons="duplicate_segment_competition;low_sample_count"),
        _diag(3, market_id="m3", reasons="weak_win_rate"),
    ]

    triage = build_wallet_flow_diagnostic_triage(diagnostics)

    assert triage.reason_counts[:2] == [("low_sample_count", 2), ("weak_win_rate", 2)]
    assert ("increase sample coverage", 2) in triage.action_bucket_counts
    assert ("insufficient forward return support", 2) in triage.action_bucket_counts
    assert ("inspect duplicate segment competition", 1) in triage.action_bucket_counts


def test_near_miss_ordering_prefers_lower_candidate_rank() -> None:
    diagnostics = [
        _diag(
            2,
            market_id="m2",
            reasons="weak_win_rate",
            grade="WATCHLIST",
            improvement=0.0008,
            net_after_cost=0.00005,
        ),
        _diag(
            1,
            market_id="m1",
            reasons="improvement_below_cost_buffer;weak_win_rate",
            grade="WATCHLIST",
            improvement=0.0009,
            net_after_cost=0.00015,
        ),
    ]

    triage = build_wallet_flow_diagnostic_triage(diagnostics, near_miss_limit=2)

    assert [item.candidate_rank for item in triage.near_misses] == [1, 2]


def test_report_is_honest_and_threshold_safe(tmp_path) -> None:
    diagnostics = [
        _diag(1, market_id="m1", reasons="weak_win_rate", grade="WATCHLIST"),
    ]
    path = write_wallet_flow_diagnostic_triage_report(
        output_dir=tmp_path,
        diagnostics=diagnostics,
    )

    report = path.read_text()
    assert path.name == "wallet_flow_diagnostic_triage.md"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in report
    assert "No promotion thresholds were changed." in report
    assert "This report explains rejection causes; it does not approve candidates." in report
    assert "candidate retained but not promoted" in report


def test_missing_diagnostics_fallback_does_not_crash(tmp_path) -> None:
    diagnostics = read_wallet_flow_rejection_diagnostics(tmp_path / "missing.csv")
    triage = build_wallet_flow_diagnostic_triage(diagnostics)
    report = render_wallet_flow_diagnostic_triage(triage)

    assert diagnostics == []
    assert "diagnostics: 0" in report
    assert "(none)" in report
