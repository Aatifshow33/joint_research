from __future__ import annotations

import json

from joint_research.research.composite_signal import (
    CompositeCandidateGrade,
    CompositeSignalResult,
    rank_composite_results,
    scan_feature_group,
    write_composite_signal_report,
)
from joint_research.research.features import FeatureInput, build_feature_rows

HOUR_NS = 3_600_000_000_000


def _input(i: int, *, price: float, close: float, fwd: float) -> FeatureInput:
    return FeatureInput(
        open_time_ns=i * HOUR_NS,
        asset="BTC",
        market_id="m1",
        market_slug="btc-test",
        token_id="tok1",
        question="BTC test?",
        end_date_iso=None,
        poly_yes_price=price,
        crypto_close=close,
        crypto_volume_quote=100.0,
        forward_return_1h=fwd,
        forward_return_4h=fwd,
        forward_return_24h=fwd,
    )


def _result(slug: str, *, score: float = 1.0) -> CompositeSignalResult:
    return CompositeSignalResult(
        rank=0,
        asset="BTC",
        market_id=slug,
        market_slug=slug,
        token_id=f"{slug}-tok",
        question=None,
        rule_family="probability_momentum_continuation",
        horizon_hours=1,
        learned_direction=1,
        train_accuracy=0.60,
        test_accuracy=0.55,
        train_average_forward_return=0.01,
        test_average_forward_return=0.008,
        stability=0.75,
        train_samples=50,
        test_samples=30,
        simplicity=1.0,
        score=score,
        grade=CompositeCandidateGrade.WATCHLIST,
        filter_reason="passed",
    )


def test_train_only_direction_learning() -> None:
    # Train window: probability rises before positive returns. Test window:
    # same direction also works. The learned direction must come from train.
    inputs = []
    for i in range(20):
        change = 0.01 if i % 2 == 0 else -0.01
        price = 0.5 + change * i
        fwd = 0.01 if change > 0 else -0.01
        inputs.append(_input(i, price=price, close=100 + i, fwd=fwd))
    rows = build_feature_rows(inputs)

    results = scan_feature_group(rows, min_train_samples=5, min_test_samples=5)

    best = results[0]
    assert best.learned_direction in {-1, 1}
    assert best.train_samples >= 5
    assert best.test_samples >= 5
    assert best.test_accuracy >= 0.5


def test_composite_ranking_is_deterministic() -> None:
    z = _result("z-market", score=2.0)
    a = _result("a-market", score=2.0)

    ranked = rank_composite_results([z, a])

    assert [row.market_slug for row in ranked] == ["a-market", "z-market"]
    assert [row.rank for row in ranked] == [1, 2]


def test_composite_artifact_writing(tmp_path) -> None:
    paths = write_composite_signal_report(
        output_dir=tmp_path / "composite",
        results=[_result("btc-test", score=2.0)],
    )

    assert paths.summary_md.name == "composite_signal_summary.md"
    assert paths.results_csv.name == "composite_signal_results.csv"
    assert paths.candidates_json.name == "composite_signal_candidates.json"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in paths.summary_md.read_text()
    assert "asset,market_id,market_slug" in paths.results_csv.read_text()
    assert json.loads(paths.candidates_json.read_text())[0]["grade"] == "WATCHLIST"


def test_empty_composite_report(tmp_path) -> None:
    paths = write_composite_signal_report(output_dir=tmp_path / "composite", results=[])

    assert "No composite candidates" in paths.summary_md.read_text()
    assert json.loads(paths.candidates_json.read_text()) == []
