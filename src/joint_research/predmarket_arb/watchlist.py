"""Verified cross-venue watchlist — the resolution-risk safety gate.

A title match is not a tradeable match: the two venues must also *resolve* the
question by the same source, criteria, and date. This module separates trusted,
human-verified pairs (the watchlist) from raw auto-matches, and produces a
side-by-side review packet of each venue's resolution rules so a candidate can
be verified before it is ever traded.

Only ``resolution_verified`` entries feed the detector's ``--manual-map``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WatchlistEntry:
    """One trusted (or pending) cross-venue market pair."""

    kalshi_ticker: str
    polymarket_key: str
    title: str
    resolution_verified: bool = False
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WatchlistEntry:
        missing = [k for k in ("kalshi_ticker", "polymarket_key", "title") if not payload.get(k)]
        if missing:
            raise ValueError(f"watchlist_entry_missing_fields: {', '.join(missing)}")
        tags = payload.get("tags") or []
        return cls(
            kalshi_ticker=str(payload["kalshi_ticker"]),
            polymarket_key=str(payload["polymarket_key"]),
            title=str(payload["title"]),
            resolution_verified=bool(payload.get("resolution_verified", False)),
            notes=str(payload.get("notes", "")),
            tags=[str(t) for t in tags],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kalshi_ticker": self.kalshi_ticker,
            "polymarket_key": self.polymarket_key,
            "title": self.title,
            "resolution_verified": self.resolution_verified,
            "notes": self.notes,
            "tags": list(self.tags),
        }


def load_watchlist(path: Path) -> list[WatchlistEntry]:
    """Load watchlist entries from a JSON list; missing file -> empty list."""
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("watchlist file must be a JSON list")
    return [WatchlistEntry.from_dict(item) for item in payload]


def save_watchlist(entries: list[WatchlistEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [entry.to_dict() for entry in entries]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verified_manual_map(entries: list[WatchlistEntry]) -> dict[str, str]:
    """Trusted ``{kalshi_ticker: polymarket_key}`` map (verified entries only)."""
    return {
        entry.kalshi_ticker: entry.polymarket_key
        for entry in entries
        if entry.resolution_verified
    }


@dataclass(frozen=True)
class ReviewCandidate:
    """A candidate pair plus both venues' resolution text, for sign-off."""

    kalshi_ticker: str
    polymarket_key: str
    title: str
    similarity: float
    net_edge_per_pair: float
    kalshi_rules: str
    polymarket_rules: str


def render_review_packet(candidates: list[ReviewCandidate]) -> str:
    """Markdown packet: each candidate's rules side by side for verification."""
    lines = [
        "# Cross-Venue Resolution Review Packet",
        "",
        "> Verify that **both** venues resolve each question by the same source,",
        "> criteria, and date. Only then add it to the watchlist with",
        "> `resolution_verified: true`. An unverified pair is directional risk.",
        "",
    ]
    if not candidates:
        lines.append("_No candidates to review._")
        return "\n".join(lines) + "\n"

    for index, c in enumerate(candidates, start=1):
        lines += [
            f"## {index}. {c.title}",
            "",
            f"- similarity: `{c.similarity:.2f}`  ·  net edge/pair: "
            f"`{c.net_edge_per_pair:+.4f}`",
            f"- kalshi_ticker: `{c.kalshi_ticker}`",
            f"- polymarket_key: `{c.polymarket_key}`",
            "",
            "**Kalshi resolution:**",
            "",
            f"> {c.kalshi_rules.strip() or '(none provided)'}",
            "",
            "**Polymarket resolution:**",
            "",
            f"> {c.polymarket_rules.strip() or '(none provided)'}",
            "",
            "- [ ] verified: both venues resolve identically",
            "",
        ]
    return "\n".join(lines) + "\n"


def fetch_kalshi_rules(
    ticker: str,
    *,
    timeout_seconds: float = 15.0,
) -> str:  # pragma: no cover - thin network wrapper
    import httpx

    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url)
        if response.status_code >= 400:
            return ""
        market = response.json().get("market", {})
    primary = str(market.get("rules_primary") or "")
    secondary = str(market.get("rules_secondary") or "")
    return "\n\n".join(part for part in (primary, secondary) if part)


def fetch_polymarket_rules(
    condition_id: str,
    *,
    timeout_seconds: float = 15.0,
) -> str:  # pragma: no cover - thin network wrapper
    import httpx

    url = "https://gamma-api.polymarket.com/markets"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url, params={"condition_ids": condition_id})
        if response.status_code >= 400:
            return ""
        body = response.json()
    rows = body if isinstance(body, list) else body.get("data", [])
    if not rows:
        return ""
    return str(rows[0].get("description") or "")
