"""Match equivalent binary markets across venues.

Matching is the hard, error-prone half of cross-venue arb: two venues word the
same event differently, and a wrong match produces a phantom "arb" that is
really directional risk on two different questions. We are deliberately
conservative:

* an explicit ``manual_map`` (kalshi_key -> polymarket_key) always wins and is
  treated as a trusted, human-reviewed link;
* otherwise we fall back to normalized-title token overlap (Jaccard) and only
  propose a match above a high similarity threshold.

The output carries the similarity and the match method so downstream review can
see *why* a pair was linked before any capital is risked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from joint_research.predmarket_arb.types import BinaryMarketQuote

DEFAULT_MIN_SIMILARITY = 0.6

MATCH_METHOD_MANUAL = "manual_map"
MATCH_METHOD_TOKEN_OVERLAP = "token_overlap"

# Generic words that carry no disambiguating signal for prediction markets.
_STOPWORDS = frozenset(
    {
        "will",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "by",
        "be",
        "is",
        "are",
        "at",
        "for",
        "and",
        "or",
        "this",
        "that",
        "before",
        "after",
        "than",
        "market",
        "yes",
        "no",
    }
)


@dataclass(frozen=True)
class MatchedMarket:
    """One linked pair of quotes across two venues."""

    market_key: str
    title: str
    quote_a: BinaryMarketQuote
    quote_b: BinaryMarketQuote
    similarity: float
    match_method: str


def normalize_title(title: str) -> frozenset[str]:
    """Lowercase, strip punctuation, drop stopwords -> a token set."""
    lowered = title.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    return frozenset(word for word in words if word and word not in _STOPWORDS)


def title_similarity(left: str, right: str) -> float:
    """Jaccard similarity of normalized title token sets, in [0, 1]."""
    left_tokens = normalize_title(left)
    right_tokens = normalize_title(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def match_markets(
    quotes_a: list[BinaryMarketQuote],
    quotes_b: list[BinaryMarketQuote],
    *,
    manual_map: dict[str, str] | None = None,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[MatchedMarket]:
    """Link quotes from venue A to venue B.

    ``manual_map`` maps ``quote_a.market_key`` -> ``quote_b.market_key`` and is
    applied first. Remaining venue-A quotes are matched by best title overlap
    above ``min_similarity``. Each venue-B quote is used at most once; the
    highest-similarity pairings are committed first.
    """

    by_key_b = {quote.market_key: quote for quote in quotes_b}
    used_b: set[str] = set()
    matches: list[MatchedMarket] = []
    manual = manual_map or {}

    remaining_a: list[BinaryMarketQuote] = []
    for quote in quotes_a:
        mapped_key = manual.get(quote.market_key)
        if mapped_key is not None and mapped_key in by_key_b and mapped_key not in used_b:
            partner = by_key_b[mapped_key]
            used_b.add(mapped_key)
            matches.append(
                MatchedMarket(
                    market_key=f"{quote.market_key}|{partner.market_key}",
                    title=quote.title,
                    quote_a=quote,
                    quote_b=partner,
                    similarity=1.0,
                    match_method=MATCH_METHOD_MANUAL,
                )
            )
        else:
            remaining_a.append(quote)

    # Greedy best-first over all candidate token-overlap pairs.
    candidates: list[tuple[float, BinaryMarketQuote, BinaryMarketQuote]] = []
    for quote in remaining_a:
        for partner in quotes_b:
            similarity = title_similarity(quote.title, partner.title)
            if similarity >= min_similarity:
                candidates.append((similarity, quote, partner))

    candidates.sort(key=lambda item: (-item[0], item[1].market_key, item[2].market_key))
    used_a: set[str] = set()
    for similarity, quote, partner in candidates:
        if quote.market_key in used_a or partner.market_key in used_b:
            continue
        used_a.add(quote.market_key)
        used_b.add(partner.market_key)
        matches.append(
            MatchedMarket(
                market_key=f"{quote.market_key}|{partner.market_key}",
                title=quote.title,
                quote_a=quote,
                quote_b=partner,
                similarity=similarity,
                match_method=MATCH_METHOD_TOKEN_OVERLAP,
            )
        )

    matches.sort(key=lambda match: match.market_key)
    return matches
