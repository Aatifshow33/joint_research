from __future__ import annotations

import json

import duckdb

from joint_research.research.wallet_flow_signal import (
    WalletFlowCandidateGrade,
    WalletFlowCoverage,
    WalletFlowObservation,
    WalletFlowSignalResult,
    WalletFlowStudyDetails,
    analyze_wallet_flow_segments,
    analyze_wallet_flow_segments_with_details,
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
    wallet_bucket: str | None = None,
    whale_bucket: str = "normal",
    copy_count: int = 0,
    unique_wallets: int = 10,
) -> WalletFlowObservation:
    resolved_wallet_bucket = wallet_bucket
    if resolved_wallet_bucket is None:
        resolved_wallet_bucket = "high" if i % 2 == 0 else "normal"
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
        unique_active_wallets=unique_wallets,
        large_trade_count=2 if abs(net_flow) > 1.5 else 0,
        whale_flow_score=net_flow / 10.0,
        copy_flow_count=copy_count,
        flow_momentum_4h=0.1 * net_flow,
        flow_momentum_24h=0.2 * net_flow,
        flow_direction="buy_dominant" if net_flow > 0 else "sell_dominant" if net_flow < 0 else "neutral",
        whale_bucket=whale_bucket,
        wallet_activity_bucket=resolved_wallet_bucket,
        copy_bucket="present" if copy_count > 0 else "absent",
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
        sample_count=80,
        train_samples=48,
        test_samples=32,
        learned_direction=1,
        train_direction_match_rate=0.70,
        test_direction_match_rate=0.65,
        train_average_forward_return=0.006,
        test_average_forward_return=0.006,
        train_win_rate=0.62,
        test_win_rate=0.60,
        full_correlation=0.20,
        train_correlation=0.18,
        test_correlation=0.16,
        train_test_direction_match=True,
        stability=0.70,
        baseline_test_average_forward_return=0.0008,
        test_improvement_over_baseline=improvement,
        net_test_improvement_after_cost=improvement - 0.004,
        unique_flow_hours=80,
        active_wallet_coverage=0.9,
        non_zero_net_flow_coverage=0.9,
        score=3.0,
        grade=WalletFlowCandidateGrade.WATCHLIST,
        filter_reason="passed",
        warnings="",
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


def test_duplicate_segment_collapse_and_group_dedup() -> None:
    rows = [
        _obs(
            i,
            net_flow=2.5 if i % 2 == 0 else -2.0,
            forward_return=0.02 if i % 2 == 0 else -0.018,
            copy_count=1 if i % 12 == 0 else 0,
        )
        for i in range(120)
    ]

    details = analyze_wallet_flow_segments_with_details(
        rows,
        min_segment_samples=24,
        min_feature_samples=36,
        train_fraction=0.6,
    )

    assert details.segment_rows_before_dedup > details.segment_rows_after_dedup
    keys = {
        (r.asset, r.market_id, r.token_id, r.horizon_hours, r.feature_name)
        for r in details.results
    }
    assert len(keys) == len(details.results)
    assert any("duplicate_segment_competition" in r.warnings for r in details.results)


def test_simpler_segment_preferred_when_edges_are_close() -> None:
    rows: list[WalletFlowObservation] = []
    for i in range(140):
        sign = 1 if i % 2 == 0 else -1
        # both buckets carry similar edge; simpler all:all should survive
        rows.append(
            _obs(
                i,
                net_flow=2.0 * sign,
                forward_return=0.010 * sign,
                wallet_bucket="high" if i % 2 == 0 else "normal",
                unique_wallets=12,
            )
        )

    results = analyze_wallet_flow_segments(
        rows,
        min_segment_samples=24,
        min_feature_samples=36,
        train_fraction=0.6,
    )
    chosen = next(r for r in results if r.feature_name == "net_flow_usdc")
    assert chosen.segment_type == "all"
    assert chosen.segment_value == "all"


def test_stronger_segment_can_override_simple_when_clear() -> None:
    rows: list[WalletFlowObservation] = []
    for i in range(160):
        if i < 100:
            sign = 1 if i % 2 == 0 else -1
            rows.append(
                _obs(
                    i,
                    net_flow=2.5 * sign,
                    forward_return=0.018 * sign,
                    wallet_bucket="high",
                    unique_wallets=15,
                )
            )
        else:
            # noisy tail weakens all:all candidate
            noisy_sign = 1 if i % 2 == 0 else -1
            rows.append(
                _obs(
                    i,
                    net_flow=2.5 * noisy_sign,
                    forward_return=-0.004 * noisy_sign,
                    wallet_bucket="normal",
                    unique_wallets=8,
                )
            )

    results = analyze_wallet_flow_segments(
        rows,
        min_segment_samples=24,
        min_feature_samples=36,
        train_fraction=0.6,
    )
    chosen = next(r for r in results if r.feature_name == "net_flow_usdc")
    assert chosen.segment_type == "active_wallet_bucket"
    assert chosen.segment_value == "high"


def test_sample_and_coverage_filters_reject_thin_rows() -> None:
    rows = [
        _obs(
            i,
            net_flow=1.0 if i % 2 == 0 else -1.0,
            forward_return=0.01,
            flow_time_ns=HOUR_NS,  # collapses unique flow hours
            unique_wallets=0,
            copy_count=1 if i == 0 else 0,
        )
        for i in range(80)
    ]

    results = analyze_wallet_flow_segments(
        rows,
        min_segment_samples=24,
        min_feature_samples=36,
        train_fraction=0.6,
    )

    assert results
    assert all(r.grade is WalletFlowCandidateGrade.REJECTED for r in results)
    assert any(
        r.filter_reason in {
            "insufficient_unique_flow_hours",
            "insufficient_active_wallet_coverage",
            "insufficient_non_zero_net_flow_coverage",
        }
        for r in results
    )


def test_warning_generation_for_thin_copy_and_instability() -> None:
    rows = [
        _obs(
            i,
            net_flow=2.0 if i % 2 == 0 else -2.0,
            forward_return=0.01 if i < 30 else -0.01,
            copy_count=1 if i in (0, 17, 49) else 0,
        )
        for i in range(80)
    ]
    results = analyze_wallet_flow_segments(
        rows,
        min_segment_samples=24,
        min_feature_samples=36,
        train_fraction=0.6,
    )

    selected = next(r for r in results if r.feature_name == "net_flow_usdc")
    assert "thin_copy_flow_warning" in selected.warnings
    assert "unstable_train_test_warning" in selected.warnings


def test_ranking_is_deterministic() -> None:
    a = _result("a-market", improvement=0.006)
    z = _result("z-market", improvement=0.006)

    ranked = rank_wallet_flow_results([z, a])

    assert [row.market_slug for row in ranked] == ["a-market", "z-market"]
    assert [row.rank for row in ranked] == [1, 2]


def test_artifact_writing_includes_coverage_and_dedup_details(tmp_path) -> None:
    study_details = WalletFlowStudyDetails(
        results=[_result("btc-market", improvement=0.006)],
        segment_rows_before_dedup=42,
        segment_rows_after_dedup=10,
        coverage=WalletFlowCoverage(
            wallet_flow_rows=1001,
            market_flow_hourly_rows=397,
            whale_flow_hourly_rows=392,
            copy_flow_rows=9,
        ),
    )
    paths = write_wallet_flow_signal_report(
        output_dir=tmp_path / "wallet_flow_signal",
        results=study_details.results,
        study_details=study_details,
    )

    summary = paths.summary_md.read_text()
    assert paths.summary_md.name == "wallet_flow_signal_summary.md"
    assert paths.results_csv.name == "wallet_flow_signal_results.csv"
    assert paths.candidates_json.name == "wallet_flow_signal_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in summary
    assert "Segment rows before de-dup: 42" in summary
    assert "wallet_flow rows: 1001" in summary
    assert "Recommended Backfill Plan" in summary
    assert "asset,market_id,market_slug" in paths.results_csv.read_text()

    candidates = json.loads(paths.candidates_json.read_text())
    assert candidates[0]["grade"] == "WATCHLIST"


def test_empty_missing_wallet_flow_behavior() -> None:
    results = analyze_wallet_flow_segments([], min_segment_samples=10, min_feature_samples=10)
    assert results == []
