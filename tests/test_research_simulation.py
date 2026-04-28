from __future__ import annotations

import json

from joint_research.research.simulation import (
    SimulationCandidate,
    SimulationGrade,
    SimulationObservation,
    SimulationResult,
    determine_side,
    rank_simulation_results,
    simulate_candidate,
    write_simulation_report,
)

HOUR_NS = 3_600_000_000_000


def _candidate(*, corr: float = 0.2, lag_hours: int = 1) -> SimulationCandidate:
    return SimulationCandidate(
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        lag_hours=lag_hours,
        signal_correlation=corr,
        robustness_grade="PROMISING",
    )


def _obs(i: int, *, change: float, ret: float, close: float = 100.0) -> SimulationObservation:
    return SimulationObservation(
        open_time_ns=i * HOUR_NS,
        poly_price_change=change,
        crypto_close=close,
        forward_log_return=ret,
    )


def test_no_lookahead_entry_timing() -> None:
    result = simulate_candidate(
        _candidate(corr=0.5, lag_hours=1),
        [_obs(0, change=0.02, ret=0.01)],
        fixed_notional=10.0,
        max_simultaneous_exposure=50.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
        min_probability_move=0.001,
    )

    assert len(result.trades) == 1
    assert result.trades[0].signal_time_ns == 0
    assert result.trades[0].entry_time_ns == HOUR_NS
    assert result.trades[0].exit_time_ns == 2 * HOUR_NS


def test_fee_and_slippage_reduce_returns() -> None:
    no_cost = simulate_candidate(
        _candidate(corr=0.5),
        [_obs(0, change=0.02, ret=0.01)],
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
    )
    costly = simulate_candidate(
        _candidate(corr=0.5),
        [_obs(0, change=0.02, ret=0.01)],
        fee_bps=10.0,
        slippage_bps=15.0,
        min_samples=1,
    )

    assert costly.trades[0].net_return < no_cost.trades[0].net_return
    assert costly.total_paper_pnl < no_cost.total_paper_pnl


def test_positive_and_negative_correlation_direction_handling() -> None:
    assert determine_side(signal_correlation=0.5, probability_change=0.01) == 1
    assert determine_side(signal_correlation=0.5, probability_change=-0.01) == -1
    assert determine_side(signal_correlation=-0.5, probability_change=0.01) == -1
    assert determine_side(signal_correlation=-0.5, probability_change=-0.01) == 1


def test_exposure_cap_skips_overlapping_trades() -> None:
    observations = [_obs(i, change=0.02, ret=0.01) for i in range(4)]

    result = simulate_candidate(
        _candidate(corr=0.5, lag_hours=4),
        observations,
        fixed_notional=10.0,
        max_simultaneous_exposure=20.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
    )

    assert len(result.trades) == 2
    assert result.skipped_exposure_cap == 2


def test_simulation_ranking_is_deterministic() -> None:
    z = SimulationResult(
        rank=0,
        asset="ETH",
        market_id="z",
        market_slug="z-market",
        token_id="tok-z",
        question=None,
        lag_hours=1,
        robustness_grade="PROMISING",
        simulation_grade=SimulationGrade.WATCHLIST,
        trade_count=10,
        win_rate=0.6,
        average_gross_return=0.01,
        average_net_return=0.008,
        total_paper_pnl=2.0,
        max_drawdown=0.5,
        sharpe_like_hourly=1.0,
        exposure_utilization=0.2,
        best_trade_pnl=0.5,
        worst_trade_pnl=-0.2,
        skipped_tiny_signal=0,
        skipped_exposure_cap=0,
        trades=[],
    )
    a = SimulationResult(
        rank=0,
        asset="BTC",
        market_id="a",
        market_slug="a-market",
        token_id="tok-a",
        question=None,
        lag_hours=1,
        robustness_grade="PROMISING",
        simulation_grade=SimulationGrade.WATCHLIST,
        trade_count=10,
        win_rate=0.6,
        average_gross_return=0.01,
        average_net_return=0.008,
        total_paper_pnl=2.0,
        max_drawdown=0.5,
        sharpe_like_hourly=1.0,
        exposure_utilization=0.2,
        best_trade_pnl=0.5,
        worst_trade_pnl=-0.2,
        skipped_tiny_signal=0,
        skipped_exposure_cap=0,
        trades=[],
    )

    ranked = rank_simulation_results([z, a])

    assert [r.market_slug for r in ranked] == ["a-market", "z-market"]
    assert [r.rank for r in ranked] == [1, 2]


def test_simulation_report_writes_required_artifacts(tmp_path) -> None:
    result = simulate_candidate(
        _candidate(corr=0.5),
        [
            _obs(
                i,
                change=0.02 if i % 2 == 0 else -0.02,
                ret=0.01 if i % 2 == 0 else -0.01,
            )
            for i in range(12)
        ],
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
    )

    paths = write_simulation_report(output_dir=tmp_path / "simulation", results=[result])

    assert paths.summary_md.name == "simulation_summary.md"
    assert paths.trades_csv.name == "simulation_trades.csv"
    assert paths.results_csv.name == "simulation_results.csv"
    assert paths.candidates_json.name == "simulation_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in paths.summary_md.read_text()
    assert "asset,market_id,market_slug" in paths.results_csv.read_text()
    assert len(json.loads(paths.candidates_json.read_text())) == 1


def test_empty_no_candidate_report(tmp_path) -> None:
    paths = write_simulation_report(output_dir=tmp_path / "simulation", results=[])

    assert "No robust candidates were available" in paths.summary_md.read_text()
    assert json.loads(paths.candidates_json.read_text()) == []
