from __future__ import annotations

import json

from joint_research.research.robustness import (
    CandidateGrade,
    RobustnessObservation,
    RobustnessResult,
    apply_quality_filter,
    grade_candidate,
    permutation_baseline,
    split_train_test,
    write_robustness_report,
)


def _obs(i: int, *, x: float, y: float, price: float | None = None) -> RobustnessObservation:
    return RobustnessObservation(
        open_time_ns=i,
        poly_price=price if price is not None else 0.5 + x,
        poly_price_change=x,
        crypto_return=y,
    )


def test_train_test_split_is_temporal() -> None:
    observations = [_obs(i, x=float(i), y=float(i)) for i in range(10)]

    train, test = split_train_test(observations, train_fraction=0.6)

    assert [o.open_time_ns for o in train] == [0, 1, 2, 3, 4, 5]
    assert [o.open_time_ns for o in test] == [6, 7, 8, 9]


def test_permutation_baseline_detects_real_signal() -> None:
    observations = [_obs(i, x=float(i), y=float(i) * 2.0) for i in range(40)]

    result = permutation_baseline(observations, n_permutations=99, seed=7)

    assert result.real_correlation > 0.99
    assert result.empirical_pvalue <= 0.02


def test_candidate_grading_is_deterministic() -> None:
    grade = grade_candidate(
        train_correlation=0.24,
        test_correlation=0.20,
        empirical_pvalue=0.03,
        rolling_stability=0.80,
        n_observations=180,
    )

    assert grade is CandidateGrade.PROMISING

    weak = grade_candidate(
        train_correlation=0.24,
        test_correlation=-0.20,
        empirical_pvalue=0.03,
        rolling_stability=0.80,
        n_observations=180,
    )
    assert weak is CandidateGrade.WEAK


def test_flat_probability_market_is_filtered() -> None:
    flat = [_obs(i, x=0.0, y=float(i), price=0.5) for i in range(100)]

    decision = apply_quality_filter(
        flat,
        min_observations=30,
        min_nonzero_changes=5,
        max_flat_fraction=0.90,
    )

    assert not decision.passed
    assert decision.reason == "flat_probability"


def test_robustness_report_writes_required_artifacts(tmp_path) -> None:
    result = RobustnessResult(
        rank=1,
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        lag_hours=1,
        n_observations=120,
        n_nonzero_changes=80,
        train_correlation=0.25,
        test_correlation=0.22,
        full_correlation=0.24,
        empirical_pvalue=0.02,
        rolling_stability=0.75,
        robustness_score=3.1,
        grade=CandidateGrade.PROMISING,
        filter_reason="passed",
        days_to_resolution_at_end=30.0,
        volume_bucket="100k-1m",
        liquidity_bucket="10k-100k",
    )

    paths = write_robustness_report(
        output_dir=tmp_path / "robustness",
        results=[result],
    )

    assert paths.summary_md.name == "robustness_summary.md"
    assert paths.results_csv.name == "robustness_results.csv"
    assert paths.candidates_json.name == "robustness_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in paths.summary_md.read_text()
    assert "asset,market_id,market_slug" in paths.results_csv.read_text()
    candidates = json.loads(paths.candidates_json.read_text())
    assert candidates[0]["grade"] == "PROMISING"
