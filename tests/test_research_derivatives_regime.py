from __future__ import annotations

import json

import duckdb

from joint_research.research.derivatives_regime import (
    RegimeCandidateGrade,
    RegimeObservation,
    RegimeSegmentResult,
    analyze_regime_segments,
    asset_to_symbol,
    load_regime_observations,
    rank_regime_results,
    write_derivatives_regime_report,
)

HOUR_NS = 3_600_000_000_000


def _obs(
    i: int,
    *,
    poly_change: float,
    forward_return: float,
    direction: str = "positive",
    intensity: str = "normal",
    basis_side: str = "premium",
    combined: str = "positive|normal|premium",
) -> RegimeObservation:
    return RegimeObservation(
        asset="BTC",
        symbol="BTCUSDT",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        open_time_ns=i * HOUR_NS,
        regime_time_ns=i * HOUR_NS,
        horizon_hours=1,
        poly_price_change=poly_change,
        forward_return=forward_return,
        funding_rate=0.00005,
        basis_pct=0.001,
        funding_direction=direction,
        funding_intensity=intensity,
        basis_side=basis_side,
        combined_regime=combined,
    )


def _result(slug: str, *, improvement: float) -> RegimeSegmentResult:
    return RegimeSegmentResult(
        rank=0,
        asset="BTC",
        symbol="BTCUSDT",
        market_id=slug,
        market_slug=slug,
        token_id=f"{slug}-tok",
        question=None,
        horizon_hours=1,
        segment_type="funding_direction",
        segment_value="positive",
        combined_regime=None,
        simplicity=1.0,
        sample_count=48,
        train_samples=28,
        test_samples=20,
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
        grade=RegimeCandidateGrade.WATCHLIST,
        filter_reason="passed",
    )


def test_asset_symbol_mapping() -> None:
    assert asset_to_symbol("btc") == "BTCUSDT"
    assert asset_to_symbol("ETH") == "ETHUSDT"


def test_timestamp_alignment_uses_nearest_prior_hour() -> None:
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
        CREATE TABLE crypto_derivatives_regime (
          symbol VARCHAR,
          event_time_ns BIGINT,
          funding_rate DOUBLE,
          basis_pct DOUBLE
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
        INSERT INTO crypto_derivatives_regime VALUES
          ('BTCUSDT', ?, 0.00010, 0.002),
          ('BTCUSDT', ?, -0.00010, -0.002)
        """,
        [9 * HOUR_NS, 11 * HOUR_NS],
    )

    rows = load_regime_observations(con)

    assert len(rows) == 1
    assert rows[0].symbol == "BTCUSDT"
    assert rows[0].regime_time_ns == 9 * HOUR_NS
    assert rows[0].funding_direction == "positive"


def test_missing_derivatives_data_gracefully_marks_unknown() -> None:
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
        CREATE TABLE crypto_derivatives_regime (
          symbol VARCHAR,
          event_time_ns BIGINT,
          funding_rate DOUBLE,
          basis_pct DOUBLE
        )
        """
    )
    con.execute(
        """
        INSERT INTO crypto_polymarket_aligned VALUES
          ('ETH', 'm2', 'eth-test', 'tok2', 'ETH test?', ?, -0.02, 0.01, NULL, NULL)
        """,
        [5 * HOUR_NS],
    )

    rows = load_regime_observations(con)

    assert len(rows) == 1
    assert rows[0].symbol == "ETHUSDT"
    assert rows[0].regime_time_ns is None
    assert rows[0].funding_direction == "unknown"
    assert rows[0].combined_regime == "unknown"


def test_regime_segmentation_and_baseline_comparison() -> None:
    observations: list[RegimeObservation] = []
    # Positive regime observations: strong positive edge.
    for i in range(8):
        observations.append(
            _obs(
                i,
                poly_change=0.02 if i % 2 == 0 else -0.02,
                forward_return=0.01 if i % 2 == 0 else -0.01,
                direction="positive",
                intensity="high",
                basis_side="premium",
                combined="positive|high|premium",
            )
        )
    # Negative regime observations: weaker/negative edge to drag baseline down.
    for i in range(8, 16):
        observations.append(
            _obs(
                i,
                poly_change=0.02 if i % 2 == 0 else -0.02,
                forward_return=-0.005 if i % 2 == 0 else 0.005,
                direction="negative",
                intensity="low",
                basis_side="discount",
                combined="negative|low|discount",
            )
        )

    results = analyze_regime_segments(
        observations,
        min_segment_samples=4,
        min_combined_samples=6,
        train_fraction=0.6,
    )

    segment_types = {row.segment_type for row in results}
    assert "funding_direction" in segment_types
    assert "funding_intensity" in segment_types
    assert "basis_side" in segment_types
    assert "combined_regime" in segment_types

    positive_direction = [
        row for row in results if row.segment_type == "funding_direction" and row.segment_value == "positive"
    ][0]
    assert positive_direction.test_improvement_over_baseline > 0


def test_minimum_sample_filtering_rejects_small_segments() -> None:
    rows = [
        _obs(
            i,
            poly_change=0.01,
            forward_return=0.01,
            direction="positive",
            intensity="normal",
            basis_side="premium",
            combined="positive|normal|premium",
        )
        for i in range(5)
    ]

    results = analyze_regime_segments(rows, min_segment_samples=6, min_combined_samples=8)
    assert results
    assert all(result.grade is RegimeCandidateGrade.REJECTED for result in results)
    assert any(result.filter_reason == "insufficient_samples" for result in results)


def test_ranking_is_deterministic() -> None:
    a = _result("a-market", improvement=0.0008)
    z = _result("z-market", improvement=0.0008)

    ranked = rank_regime_results([z, a])

    assert [row.market_slug for row in ranked] == ["a-market", "z-market"]
    assert [row.rank for row in ranked] == [1, 2]


def test_artifact_writing(tmp_path) -> None:
    paths = write_derivatives_regime_report(
        output_dir=tmp_path / "derivatives_regime",
        results=[_result("btc-market", improvement=0.001)],
    )

    assert paths.summary_md.name == "derivatives_regime_summary.md"
    assert paths.results_csv.name == "derivatives_regime_results.csv"
    assert paths.candidates_json.name == "derivatives_regime_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in paths.summary_md.read_text()
    assert "asset,symbol,market_id" in paths.results_csv.read_text()
    candidates = json.loads(paths.candidates_json.read_text())
    assert candidates[0]["grade"] == "WATCHLIST"
