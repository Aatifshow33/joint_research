from __future__ import annotations

import json
from pathlib import Path

from joint_research.research.simulation import (
    SimulationCandidate,
    SimulationGrade,
    SimulationObservation,
    SimulationResult,
    _dedupe_wallet_candidates,
    _load_candidates,
    _wallet_segment_match,
    determine_side,
    rank_simulation_results,
    run_simulation_study,
    simulate_candidate,
    write_simulation_report,
)
from joint_research.warehouse import CRYPTO_OHLCV, POLYMARKET_PRICE_HISTORY, ParquetWriter, WarehousePaths

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


def test_wallet_feature_direction_handling() -> None:
    candidate = SimulationCandidate(
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        lag_hours=1,
        signal_correlation=0.0,
        robustness_grade="WATCHLIST",
        candidate_source="wallet-flow-signal",
        feature_name="net_flow_usdc",
        learned_direction=-1,
    )
    obs = SimulationObservation(
        open_time_ns=0,
        poly_price_change=0.01,
        crypto_close=100.0,
        forward_log_return=-0.01,
        net_flow_usdc=1000.0,
    )

    result = simulate_candidate(
        candidate,
        [obs],
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
    )

    assert len(result.trades) == 1
    assert result.trades[0].side == -1


def test_segment_filter_applied_correctly() -> None:
    candidate = SimulationCandidate(
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        lag_hours=1,
        signal_correlation=0.0,
        robustness_grade="WATCHLIST",
        candidate_source="wallet-flow-signal",
        feature_name="net_flow_usdc",
        segment_type="flow_direction",
        segment_value="buy_dominant",
        learned_direction=1,
    )
    buy_obs = SimulationObservation(
        open_time_ns=0,
        poly_price_change=0.01,
        crypto_close=100.0,
        forward_log_return=0.01,
        net_flow_usdc=100.0,
        flow_direction="buy_dominant",
    )
    sell_obs = SimulationObservation(
        open_time_ns=HOUR_NS,
        poly_price_change=0.01,
        crypto_close=100.0,
        forward_log_return=0.01,
        net_flow_usdc=-100.0,
        flow_direction="sell_dominant",
    )

    assert _wallet_segment_match(candidate, buy_obs)
    assert not _wallet_segment_match(candidate, sell_obs)


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


def test_duplicate_candidate_suppression() -> None:
    candidates = [
        SimulationCandidate(
            asset="BTC",
            market_id="m1",
            market_slug="btc",
            token_id="t1",
            question=None,
            lag_hours=1,
            signal_correlation=0.0,
            robustness_grade="WATCHLIST",
            candidate_source="wallet-flow-signal",
            feature_name="net_flow_usdc",
            segment_type="all",
            segment_value="all",
            learned_direction=-1,
        ),
        SimulationCandidate(
            asset="BTC",
            market_id="m1",
            market_slug="btc",
            token_id="t1",
            question=None,
            lag_hours=1,
            signal_correlation=0.0,
            robustness_grade="WATCHLIST",
            candidate_source="wallet-flow-signal",
            feature_name="net_flow_usdc",
            segment_type="whale_flow_bucket",
            segment_value="normal",
            learned_direction=-1,
        ),
    ]

    deduped = _dedupe_wallet_candidates(candidates)
    assert len(deduped) == 1


def test_wallet_flow_candidate_source_selection(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path / "data" / "warehouse")
    artifact_dir = tmp_path / "artifacts" / "research" / "wallet_flow_signal"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    candidate_payload = [
        {
            "asset": "BTC",
            "market_id": "m1",
            "market_slug": "btc",
            "token_id": "tok1",
            "question": "q",
            "horizon_hours": 1,
            "feature_name": "net_flow_usdc",
            "segment_type": "all",
            "segment_value": "all",
            "learned_direction": -1,
            "grade": "SIMULATION_READY",
        }
    ]
    (artifact_dir / "wallet_flow_signal_candidates.json").write_text(
        json.dumps(candidate_payload) + "\n"
    )

    candidates = _load_candidates(paths=paths, source="wallet-flow-signal")
    assert len(candidates) == 1
    assert candidates[0].candidate_source == "wallet-flow-signal"
    assert candidates[0].feature_name == "net_flow_usdc"


def test_default_simulation_behavior_unchanged_runs_robustness_source(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path / "data" / "warehouse")
    # Minimal seeded market/returns so the pipeline runs even if it yields no candidates.
    writer_ohlcv = ParquetWriter(table=CRYPTO_OHLCV, paths=paths)
    writer_ohlcv.write(
        [
            {
                "event_time_ns": 0,
                "source": "test",
                "payload_hash": "a",
                "payload_json": "[]",
                "venue": "binance",
                "symbol": "BTCUSDT",
                "interval": "1h",
                "open_time_ns": 0,
                "close_time_ns": HOUR_NS - 1,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume_base": 1.0,
                "volume_quote": 100.0,
                "num_trades": 1,
                "taker_buy_volume_base": 0.5,
                "taker_buy_volume_quote": 50.0,
            }
        ]
    )
    writer_price = ParquetWriter(table=POLYMARKET_PRICE_HISTORY, paths=paths)
    writer_price.write(
        [
            {
                "event_time_ns": 0,
                "source": "test",
                "payload_hash": "b",
                "payload_json": "{}",
                "token_id": "tok1",
                "market_id": "m1",
                "outcome": "Yes",
                "price": 0.5,
                "interval_label": "1h",
                "fidelity_minutes": 60,
            }
        ]
    )

    results = run_simulation_study(paths=paths)
    assert isinstance(results, list)


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


def test_wallet_flow_report_prefix(tmp_path) -> None:
    result = simulate_candidate(
        _candidate(corr=0.5),
        [_obs(i, change=0.02, ret=0.01) for i in range(12)],
        fee_bps=0.0,
        slippage_bps=0.0,
        min_samples=1,
    )
    paths = write_simulation_report(
        output_dir=tmp_path / "simulation_wallet_flow",
        results=[result],
        file_prefix="simulation_wallet_flow",
    )
    assert paths.summary_md.name == "simulation_wallet_flow_summary.md"
    assert paths.trades_csv.name == "simulation_wallet_flow_trades.csv"
    assert paths.results_csv.name == "simulation_wallet_flow_results.csv"
    assert paths.candidates_json.name == "simulation_wallet_flow_candidates.json"


def test_empty_no_candidate_report(tmp_path) -> None:
    paths = write_simulation_report(output_dir=tmp_path / "simulation", results=[])

    assert "No robust candidates were available" in paths.summary_md.read_text()
    assert json.loads(paths.candidates_json.read_text()) == []
