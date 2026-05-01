
from __future__ import annotations

from joint_research.research.wallet_flow_promotion_plan import (
    build_wallet_flow_promotion_plan,
    render_wallet_flow_promotion_plan,
    write_wallet_flow_promotion_plan_report,
)
from joint_research.research.wallet_flow_signal import WalletFlowRejectionDiagnostic


def _diagnostic(
    *,
    rank: int = 1,
    final_grade: str = "REJECTED",
    reasons: str = "low_sample_count;no_net_improvement_after_cost",
    retained: bool = False,
) -> WalletFlowRejectionDiagnostic:
    return WalletFlowRejectionDiagnostic(
        rank=rank,
        asset="BTC",
        market_id=f"market-{rank}",
        market_slug=f"market-{rank}",
        token_id=f"token-{rank}",
        horizon_hours=4,
        feature_name="net_flow",
        segment_type="wallet",
        segment_value=f"wallet-{rank}",
        final_grade=final_grade,
        retained_after_dedup=retained,
        rejection_reasons=reasons,
        sample_count=12,
        test_samples=4,
        unique_flow_hours=3,
        active_wallet_coverage=0.1,
        non_zero_net_flow_coverage=0.2,
        test_improvement_over_baseline=0.001,
        net_test_improvement_after_cost=-0.002,
        test_win_rate=0.48,
        stability=0.2,
    )


def test_promotion_plan_keeps_hard_non_tradeable_copy() -> None:
    plan = build_wallet_flow_promotion_plan([_diagnostic()])
    rendered = render_wallet_flow_promotion_plan(plan)

    assert "EXPLORATORY ONLY - NOT TRADEABLE" in rendered
    assert "No thresholds changed." in rendered
    assert "No candidates approved." in rendered
    assert "This is a data/action plan only." in rendered
    assert "No wallet-flow candidate should be promoted from this report alone." in rendered


def test_promotion_plan_orders_actions_and_blockers() -> None:
    diagnostics = [
        _diagnostic(rank=1, reasons="low_sample_count;no_net_improvement_after_cost"),
        _diagnostic(rank=2, reasons="low_sample_count;weak_stability"),
        _diagnostic(rank=3, reasons="duplicate_segment_competition"),
    ]

    plan = build_wallet_flow_promotion_plan(diagnostics)

    assert plan.action_counts[0] == ("backfill more wallet-flow history", 2)
    assert ("keep rejected until net edge clears costs", 1) in plan.action_counts
    assert ("coverage too thin", 2) in plan.blocker_counts
    assert ("more total segment samples", 2) in plan.data_gap_counts


def test_promotion_plan_tracks_retained_non_promoted() -> None:
    diagnostics = [
        _diagnostic(rank=1, final_grade="WATCHLIST", retained=True),
        _diagnostic(rank=2, final_grade="REJECTED", retained=False),
    ]

    plan = build_wallet_flow_promotion_plan(diagnostics)

    assert plan.retained_non_promoted == 1
    assert (
        "rerun after backfill because candidate was retained but not promoted",
        1,
    ) in plan.action_counts


def test_write_promotion_plan_report(tmp_path) -> None:
    report_path = write_wallet_flow_promotion_plan_report(
        output_dir=tmp_path,
        diagnostics=[_diagnostic()],
    )

    assert report_path == tmp_path / "wallet_flow_promotion_plan.md"
    assert report_path.exists()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in report_path.read_text()
