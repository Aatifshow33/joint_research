from __future__ import annotations

from joint_research.predmarket_arb.detector import (
    DIRECTION_YES_B_NO_A,
    REASON_ACTIONABLE,
    REASON_BANKROLL_TOO_SMALL,
    REASON_EDGE_BELOW_THRESHOLD,
    REASON_NEGATIVE_GROSS_EDGE,
    REASON_PROFIT_BELOW_MINIMUM,
    REASON_ZERO_AVAILABLE_SIZE,
    DetectorConfig,
    evaluate_market_pair,
)
from joint_research.predmarket_arb.types import BinaryMarketQuote


def _kalshi(yes: float, no: float, *, size: int = 1000) -> BinaryMarketQuote:
    return BinaryMarketQuote(
        venue="kalshi",
        market_key="BTC-100K",
        title="Bitcoin above 100k",
        yes_ask=yes,
        no_ask=no,
        yes_size=size,
        no_size=size,
        event_time_ns=1,
    )


def _polymarket(yes: float, no: float, *, size: int = 1000) -> BinaryMarketQuote:
    return BinaryMarketQuote(
        venue="polymarket",
        market_key="0xbtc",
        title="Will Bitcoin be above 100k",
        yes_ask=yes,
        no_ask=no,
        yes_size=size,
        no_size=size,
        event_time_ns=1,
    )


def test_clear_cross_venue_arb_is_actionable() -> None:
    # YES cheaper on Polymarket (0.40), NO cheaper on Kalshi (0.43): pair costs
    # 0.83 gross, well under $1 even after Kalshi fees.
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.58, no=0.43),
        _polymarket(yes=0.40, no=0.60),
        config=DetectorConfig(bankroll_usd=200.0),
    )
    assert evaluation.is_actionable is True
    assert evaluation.reason_code == REASON_ACTIONABLE
    assert evaluation.direction == DIRECTION_YES_B_NO_A
    assert evaluation.venue_yes == "polymarket"
    assert evaluation.venue_no == "kalshi"
    assert evaluation.contracts > 0
    assert evaluation.net_profit_usd > 0
    # Fee-inclusive capital must never exceed the bankroll.
    assert evaluation.capital_required_usd <= 200.0 + 1e-9
    assert evaluation.net_edge_per_pair >= 0.02


def test_positive_gross_edge_killed_by_fees_is_below_threshold() -> None:
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.55, no=0.50),
        _polymarket(yes=0.49, no=0.51),
        config=DetectorConfig(bankroll_usd=200.0),
    )
    assert evaluation.gross_edge_per_pair > 0
    assert evaluation.is_actionable is False
    assert evaluation.reason_code == REASON_EDGE_BELOW_THRESHOLD


def test_negative_gross_edge_is_flagged() -> None:
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.60, no=0.55),
        _polymarket(yes=0.55, no=0.60),
    )
    assert evaluation.reason_code == REASON_NEGATIVE_GROSS_EDGE
    assert evaluation.contracts == 0


def test_bankroll_too_small_to_afford_one_pair() -> None:
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.58, no=0.43),
        _polymarket(yes=0.40, no=0.60),
        config=DetectorConfig(bankroll_usd=0.50),
    )
    assert evaluation.reason_code == REASON_BANKROLL_TOO_SMALL
    assert evaluation.contracts == 0


def test_zero_available_size_is_flagged() -> None:
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.58, no=0.43),
        _polymarket(yes=0.40, no=0.60, size=0),
        config=DetectorConfig(bankroll_usd=200.0),
    )
    assert evaluation.reason_code == REASON_ZERO_AVAILABLE_SIZE


def test_actionable_edge_but_profit_below_minimum() -> None:
    # Strong per-pair edge, but only one contract of depth and a $1 floor.
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.58, no=0.43, size=1),
        _polymarket(yes=0.40, no=0.60, size=1),
        config=DetectorConfig(bankroll_usd=200.0, min_net_profit_usd=1.0),
    )
    assert evaluation.contracts == 1
    assert evaluation.net_edge_per_pair >= 0.02
    assert evaluation.is_actionable is False
    assert evaluation.reason_code == REASON_PROFIT_BELOW_MINIMUM


def test_max_contracts_caps_position() -> None:
    evaluation = evaluate_market_pair(
        _kalshi(yes=0.58, no=0.43),
        _polymarket(yes=0.40, no=0.60),
        config=DetectorConfig(bankroll_usd=200.0, max_contracts=10),
    )
    assert evaluation.contracts == 10
    assert evaluation.is_actionable is True
