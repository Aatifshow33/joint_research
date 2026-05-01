from __future__ import annotations

from pathlib import Path

from joint_research.research.wallet_flow_backfill_priority import (
    WalletFlowBackfillPriorityThresholds,
    build_wallet_flow_backfill_priority_plan,
    render_wallet_flow_backfill_priority_report,
)
from joint_research.research.wallet_flow_coverage_gate import WalletFlowCoverageRow


def _row(market_id: str, market_slug: str, asset: str, wallet_flow_rows: int = 0, market_flow_hourly_rows: int = 0, whale_flow_hourly_rows: int = 0) -> WalletFlowCoverageRow:
    return WalletFlowCoverageRow(
        market_id=market_id,
        market_slug=market_slug,
        asset=asset,
        is_active=True,
        is_closed=False,
        volume_1mo_usd=0.0,
        volume_total_usd=0.0,
        wallet_flow_rows=wallet_flow_rows,
        trade_rows=wallet_flow_rows,
        copy_rows=0,
        market_flow_hourly_rows=market_flow_hourly_rows,
        whale_flow_hourly_rows=whale_flow_hourly_rows,
    )


def test_priority_plan_ranks_missing_wallet_rows_before_hourly_thin() -> None:
    plan = build_wallet_flow_backfill_priority_plan(
        coverage_csv=Path("coverage.csv"),
        rows=[
            _row("m2", "eth-hourly-thin", "ETH", wallet_flow_rows=24),
            _row("m1", "btc-missing-wallet", "BTC"),
        ],
        thresholds=WalletFlowBackfillPriorityThresholds(),
    )

    assert plan.priorities[0].market_id == "m1"
    assert "wallet-flow rows below target" in plan.priorities[0].reasons
    assert plan.priorities[1].market_id == "m2"


def test_priority_plan_respects_top_limit() -> None:
    plan = build_wallet_flow_backfill_priority_plan(
        coverage_csv=Path("coverage.csv"),
        rows=[
            _row("m1", "btc-one", "BTC"),
            _row("m2", "eth-two", "ETH"),
            _row("m3", "sol-three", "SOL"),
        ],
        thresholds=WalletFlowBackfillPriorityThresholds(),
        top_limit=2,
    )

    assert len(plan.priorities) == 2
    assert [priority.rank for priority in plan.priorities] == [1, 2]
    assert plan.backfill_markets == 3


def test_priority_report_includes_safety_copy() -> None:
    plan = build_wallet_flow_backfill_priority_plan(
        coverage_csv=Path("coverage.csv"),
        rows=[_row("m1", "btc-missing-wallet", "BTC")],
        thresholds=WalletFlowBackfillPriorityThresholds(),
    )

    rendered = render_wallet_flow_backfill_priority_report(plan, WalletFlowBackfillPriorityThresholds())

    assert "EXPLORATORY ONLY - NOT TRADEABLE" in rendered
    assert "No candidates promoted." in rendered
    assert "No threshold changes." in rendered
    assert "No live trading changes." in rendered
    assert "This report ranks data backfill needs only." in rendered
