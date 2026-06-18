from __future__ import annotations

from joint_research.predmarket_arb.matcher import (
    MATCH_METHOD_MANUAL,
    MATCH_METHOD_TOKEN_OVERLAP,
    match_markets,
    normalize_title,
    title_similarity,
)
from joint_research.predmarket_arb.types import BinaryMarketQuote


def _quote(venue: str, key: str, title: str) -> BinaryMarketQuote:
    return BinaryMarketQuote(
        venue=venue,
        market_key=key,
        title=title,
        yes_ask=0.5,
        no_ask=0.5,
        yes_size=100,
        no_size=100,
        event_time_ns=1,
    )


def test_normalize_drops_stopwords_and_punctuation() -> None:
    tokens = normalize_title("Will Bitcoin be above $100,000?")
    assert tokens == frozenset({"bitcoin", "above", "100", "000"})


def test_title_similarity_identical_and_disjoint() -> None:
    assert title_similarity("Bitcoin above 100k", "Bitcoin above 100k") == 1.0
    assert title_similarity("Bitcoin up", "Ethereum down") == 0.0


def test_manual_map_takes_priority() -> None:
    a = [_quote("kalshi", "K1", "totally different words here")]
    b = [_quote("polymarket", "P1", "nothing in common at all")]
    matches = match_markets(a, b, manual_map={"K1": "P1"})
    assert len(matches) == 1
    assert matches[0].match_method == MATCH_METHOD_MANUAL
    assert matches[0].similarity == 1.0


def test_token_overlap_matches_above_threshold() -> None:
    a = [_quote("kalshi", "K1", "Bitcoin above $100,000 on Dec 31 2026")]
    b = [_quote("polymarket", "P1", "Will Bitcoin be above $100,000 on December 31, 2026?")]
    matches = match_markets(a, b, min_similarity=0.6)
    assert len(matches) == 1
    assert matches[0].match_method == MATCH_METHOD_TOKEN_OVERLAP
    assert matches[0].similarity >= 0.6


def test_low_overlap_is_not_matched() -> None:
    a = [_quote("kalshi", "K1", "Fed cuts rates in 2026")]
    b = [_quote("polymarket", "P1", "Will Bitcoin be above $100,000 in 2026?")]
    assert match_markets(a, b, min_similarity=0.6) == []


def test_each_venue_b_market_used_at_most_once() -> None:
    a = [
        _quote("kalshi", "K1", "Bitcoin above 100000 in 2026"),
        _quote("kalshi", "K2", "Bitcoin above 100000 in 2026"),
    ]
    b = [_quote("polymarket", "P1", "Bitcoin above 100000 in 2026")]
    matches = match_markets(a, b, min_similarity=0.6)
    assert len(matches) == 1
