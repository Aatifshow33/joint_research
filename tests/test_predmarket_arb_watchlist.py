from __future__ import annotations

from pathlib import Path

import pytest
from joint_research.predmarket_arb.watchlist import (
    ReviewCandidate,
    WatchlistEntry,
    load_watchlist,
    render_review_packet,
    save_watchlist,
    verified_manual_map,
)


def test_round_trip_save_and_load(tmp_path: Path) -> None:
    entries = [
        WatchlistEntry("KX-A", "0xaaa", "Question A", resolution_verified=True, notes="ok"),
        WatchlistEntry("KX-B", "0xbbb", "Question B", resolution_verified=False),
    ]
    path = tmp_path / "wl.json"
    save_watchlist(entries, path)
    loaded = load_watchlist(path)
    assert loaded == entries


def test_missing_file_is_empty_list(tmp_path: Path) -> None:
    assert load_watchlist(tmp_path / "nope.json") == []


def test_verified_manual_map_only_includes_verified() -> None:
    entries = [
        WatchlistEntry("KX-A", "0xaaa", "A", resolution_verified=True),
        WatchlistEntry("KX-B", "0xbbb", "B", resolution_verified=False),
    ]
    assert verified_manual_map(entries) == {"KX-A": "0xaaa"}


def test_from_dict_requires_core_fields() -> None:
    with pytest.raises(ValueError, match="watchlist_entry_missing_fields"):
        WatchlistEntry.from_dict({"kalshi_ticker": "KX-A"})


def test_render_review_packet_lists_both_rule_sets() -> None:
    packet = render_review_packet(
        [
            ReviewCandidate(
                kalshi_ticker="KX-A",
                polymarket_key="0xaaa",
                title="Will X happen?",
                similarity=0.9,
                net_edge_per_pair=0.05,
                kalshi_rules="Resolves yes if X per source S by date D.",
                polymarket_rules="Resolves yes if X per source T.",
            )
        ]
    )
    assert "Will X happen?" in packet
    assert "source S" in packet
    assert "source T" in packet
    assert "[ ] verified" in packet


def test_render_review_packet_handles_empty() -> None:
    assert "No candidates" in render_review_packet([])
