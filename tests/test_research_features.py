from __future__ import annotations

from joint_research.research.features import (
    FeatureInput,
    build_feature_rows,
    is_flat_market,
    split_feature_train_test,
)

HOUR_NS = 3_600_000_000_000


def _row(i: int, *, price: float, close: float, volume: float = 100.0) -> FeatureInput:
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
        crypto_volume_quote=volume,
        forward_return_1h=0.01,
        forward_return_4h=0.02,
        forward_return_24h=0.03,
    )


def test_feature_calculations_use_only_history() -> None:
    rows = build_feature_rows(
        [
            _row(0, price=0.50, close=100.0),
            _row(1, price=0.55, close=102.0),
            _row(2, price=0.53, close=101.0),
            _row(3, price=0.60, close=106.0, volume=400.0),
        ]
    )

    last = rows[-1]
    assert last.prob_change_1h == 0.07
    assert last.prob_change_4h == 0.10
    assert last.crypto_return_1h > 0
    assert last.probability_momentum > 0
    assert last.probability_reversal < 0
    assert last.probability_level_bucket == "high"
    assert last.large_probability_move
    assert last.volume_spike


def test_feature_train_test_split_is_temporal() -> None:
    features = build_feature_rows(
        [_row(i, price=0.5 + i * 0.01, close=100.0 + i) for i in range(10)]
    )

    train, test = split_feature_train_test(features, train_fraction=0.6)

    assert [row.open_time_ns for row in train] == [
        0,
        HOUR_NS,
        2 * HOUR_NS,
        3 * HOUR_NS,
        4 * HOUR_NS,
        5 * HOUR_NS,
    ]
    assert [row.open_time_ns for row in test] == [
        6 * HOUR_NS,
        7 * HOUR_NS,
        8 * HOUR_NS,
        9 * HOUR_NS,
    ]


def test_flat_market_filter() -> None:
    flat = build_feature_rows([_row(i, price=0.5, close=100.0 + i) for i in range(40)])
    moving = build_feature_rows(
        [_row(i, price=0.5 + i * 0.002, close=100.0 + i) for i in range(40)]
    )

    assert is_flat_market(flat, max_flat_fraction=0.90)
    assert not is_flat_market(moving, max_flat_fraction=0.90)
