from __future__ import annotations

import json

import duckdb

from joint_research.research.wallet_flow_signal import (
    WalletFlowCandidateGrade,
    WalletFlowObservation,
    WalletFlowSignalResult,
    analyze_wallet_flow_segments,
    load_wallet_flow_observations,
    rank_wallet_flow_results,
    write_wallet_flow_signal_report,
)

HOUR_NS = 3_600_000_000_000


def _obs(
    i: int,
    *,
    net_flow: float,
    forward_return: float,
    flow_time_ns: int | None = None,
    whale_bucket: str = "normal",
) -> WalletFlowObservation:
    return WalletFlowObservation(
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        open_time_ns=i * HOUR_NS,
        flow_time_ns=flow_time_ns if flow_time_ns is not None else i * HOUR_NS,
        horizon_hours=1,
        poly_price_change=0.02 if i % 2 == 0 else -0.02,
        forward_return=forward_return,
        buy_volume_usdc=max(net_flow, 0.0),
        sell_volume_usdc=abs(min(net_flow, 0.0)),
        net_flow_usdc=net_flow,
        abs_net_flow_usdc=abs(net_flow),
        unique_active_wallets=10 + (i % 3),
        large_trade_count=2 if abs(net_flow) > 1.5 else 0,
        whale_flow_score=net_flow / 10.0,
        copy_flow_count=1 if i % 5 == 0 else 0,
        flow_momentum_4h=0.1 * net_flow,
        flow_momentum_24h=0.2 * net_flow,
        flow_direction="buy_dominant" if net_flow > 0 else "sell_dominant" if net_flow < 0 else "neutral",
        whale_bucket=whale_bucket,
        wallet_activity_bucket="high" if i % 2 == 0 else "normal",
        copy_bucket="present" if i % 5 == 0 else "absent",
    )


def _result(slug: str, *, improvement: float) -> WalletFlowSignalResult:
    return WalletFlowSignalResult(
        rank=0,
        asset="BTC",
        market_id=slug,
        market_slug=slug,
        token_id=f"{slug}-tok",
        question=None,
        horizon_hours=1,
        feature_name="net_flow_usdc",
        segment_type="flow_direction",
        segment_value="buy_dominant",
        simplicity=1.0,
        sample_count=60,
        train_samples=36,
        test_samples=24,
        learned_direction=1,
        train_direction_match_rate=0.65,
        test_direction_match_rate=0.60,
        train_average_forward_return=0.001,
        test_average_forward_return=0.001,
        train_win_rate=0.60,
        test_win_rate=0.58,
        full_correlation=0.10,
        train_correlation=0.10,
        test_correlation=0.09,
        train_test_direction_match=True,
        stability=0.70,
        baseline_test_average_forward_return=0.0002,
        test_improvement_over_baseline=improvement,
        score=3.0,
        grade=WalletFlowCandidateGrade.WATCHLIST,
        filter_reason="passed",
    )


def test_wallet_flow_timestamp_alignment_nearest_prior_hour() -> None:
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE crypto_polymarket_aligned (
          asset VARCHAR,
          market_id VARCHAR,
          market_slug VARCHAR,
          token_id VARCHAR,
          question VARCHAR,
          open_time_ns BIGINT,
          poly_price_change DOUBLE,
          crypto_log_return_next_1h DOUBLE,
          crypto_log_return_next_4h DOUBLE,
          crypto_log_return_next_24h DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE polymarket_market_flow_hourly (
          market_id VARCHAR,
          asset VARCHAR,
          open_time_ns BIGINT,
          buy_volume_usdc DOUBLE,
          sell_volume_usdc DOUBLE,
          net_flow_usdc DOUBLE,
          unique_active_wallets BIGINT,
          large_trade_count BIGINT,
          whale_flow_score DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE polymarket_copy_flow_events (
          market_id VARCHAR,
          asset VARCHAR,
          event_time_ns BIGINT
        )
        """
    )

    con.execute(
        """
        INSERT INTO crypto_polymarket_aligned VALUES
          ('BTC', 'm1', 'btc-test', 'tok1', 'BTC test?', ?, 0.01, 0.02, NULL, NULL)
        """,
        [10 * HOUR_NS],
    )
    con.execute(
        """
        INSERT INTO polymarket_market_flow_hourly VALUES
          ('m1', 'BTC', ?, 100, 20, 80, 5, 1, 0.7),
          ('m1', 'BTC', ?, 10, 50, -40, 3, 0, -0.4)
        """,
        [9 * HOUR_NS, 11 * HOUR_NS],
    )

    rows = load_wallet_flow_observations(con)

    assert len(rows) == 1
    assert rows[0].flow_time_ns == 9 * HOUR_NS
    assert rows[0].net_flow_usdc == 80


def test_flow_feature_calculation_and_whale_segmentation() -> None:
    rows = [
        _obs(i, net_flow=2.0 if i % 2 == 0 else -1.0, forward_return=0.01 if i % 2 == 0 else -0.01, whale_bucket="high" if i % 3 == 0 else "normal")
        for i in range(20)
    ]

    results = analyze_wallet_flow_segments(
        rows,
        min_segment_samples=6,
        min_feature_samples=8,
        train_fraction=0.6,
    )

    assert any(result.feature_name == "net_flow_usdc" for result in results)
    assert any(result.segment_type == "whale_flow_bucket" for result in results)


def test_baseline_comparison_and_minimum_sample_filtering() -> None:
    small = [_obs(i, net_flow=1.0, forward_return=0.005) for i in range(5)]
    results = analyze_wallet_flow_segments(
        small,
        min_segment_samples=6,
        min_feature_samples=8,
    )

    assert results
    assert all(result.grade is WalletFlowCandidateGrade.REJECTED for result in results)
    assert any(result.filter_reason == "insufficient_samples" for result in results)


def test_ranking_is_deterministic() -> None:
    a = _result("a-market", improvement=0.001)
    z = _result("z-market", improvement=0.001)

    ranked = rank_wallet_flow_results([z, a])

    assert [row.market_slug for row in ranked] == ["a-market", "z-market"]
    assert [row.rank for row in ranked] == [1, 2]


def test_artifact_writing_and_empty_behavior(tmp_path) -> None:
    paths = write_wallet_flow_signal_report(
        output_dir=tmp_path / "wallet_flow_signal",
        results=[_result("btc-market", improvement=0.001)],
    )

    assert paths.summary_md.name == "wallet_flow_signal_summary.md"
    assert paths.results_csv.name == "wallet_flow_signal_results.csv"
    assert paths.candidates_json.name == "wallet_flow_signal_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in paths.summary_md.read_text()
    assert "asset,market_id,market_slug" in paths.results_csv.read_text()
    candidates = json.loads(paths.candidates_json.read_text())
    assert candidates[0]["grade"] == "WATCHLIST"

    empty_paths = write_wallet_flow_signal_report(
        output_dir=tmp_path / "wallet_flow_signal_empty",
        results=[],
    )
    assert "No wallet-flow candidate" in empty_paths.summary_md.read_text()
    assert json.loads(empty_paths.candidates_json.read_text()) == []


def test_empty_missing_wallet_flow_behavior() -> None:
    results = analyze_wallet_flow_segments([], min_segment_samples=10, min_feature_samples=10)
    assert results == []
