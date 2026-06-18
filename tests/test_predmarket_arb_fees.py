from __future__ import annotations

import pytest
from joint_research.predmarket_arb.fees import (
    KalshiFeeModel,
    PolymarketFeeModel,
    fee_model_for_venue,
)


def test_kalshi_fee_matches_published_formula() -> None:
    model = KalshiFeeModel()
    # 0.07 * 100 * 0.5 * 0.5 = 1.75 exactly.
    assert model.taker_fee(price=0.5, contracts=100) == pytest.approx(1.75)


def test_kalshi_fee_rounds_up_to_the_cent() -> None:
    model = KalshiFeeModel()
    # 0.07 * 1 * 0.4 * 0.6 = 0.0168 -> rounds UP to 0.02.
    assert model.taker_fee(price=0.4, contracts=1) == pytest.approx(0.02)


def test_kalshi_fee_is_zero_for_zero_contracts() -> None:
    assert KalshiFeeModel().taker_fee(price=0.5, contracts=0) == 0.0


def test_kalshi_fee_peaks_at_the_midpoint() -> None:
    model = KalshiFeeModel()
    mid = model.taker_fee(price=0.5, contracts=1000)
    tail = model.taker_fee(price=0.1, contracts=1000)
    assert mid > tail


def test_polymarket_fee_defaults_to_zero() -> None:
    assert PolymarketFeeModel().taker_fee(price=0.42, contracts=1000) == 0.0


def test_polymarket_fee_applies_rate_and_flat_cost() -> None:
    model = PolymarketFeeModel(rate=0.01, flat_order_cost=0.25)
    # 0.01 * 100 * 0.5 + 0.25 = 0.75.
    assert model.taker_fee(price=0.5, contracts=100) == pytest.approx(0.75)


def test_fee_model_for_known_venues() -> None:
    assert fee_model_for_venue("Kalshi").venue == "kalshi"
    assert fee_model_for_venue("polymarket").venue == "polymarket"


def test_fee_model_for_unknown_venue_raises() -> None:
    with pytest.raises(ValueError, match="no_fee_model_for_venue"):
        fee_model_for_venue("ftx")


def test_fee_rejects_out_of_range_price() -> None:
    with pytest.raises(ValueError, match="price_out_of_range"):
        KalshiFeeModel().taker_fee(price=1.5, contracts=1)
