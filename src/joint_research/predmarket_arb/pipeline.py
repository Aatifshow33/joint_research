"""Live pipeline: scan -> verified watchlist -> real depth -> alerts.

This is the operating loop that turns the detector into something that catches
money continuously:

1. fetch both venues and run the broad fee-aware scan;
2. trust only ``resolution_verified`` watchlist pairs as confirmed matches;
3. refine the top candidates with **real** Polymarket CLOB depth so sizing is
   not an assumption;
4. emit alerts for actionable opportunities to an append-only log.

The depth-refinement and alert-shaping logic is pure (injected fetchers); only
``run_live_pipeline`` touches the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from joint_research.predmarket_arb.detector import (
    REASON_PROFIT_BELOW_MINIMUM,
    ArbEvaluation,
    DetectorConfig,
    evaluate_market_pair,
)
from joint_research.predmarket_arb.matcher import MatchedMarket
from joint_research.predmarket_arb.types import BinaryMarketQuote

# (token_id, max_price) -> fillable contract count.
FillableFetcher = Callable[[str, float], int | None]


@dataclass(frozen=True)
class Alert:
    """One actionable opportunity worth surfacing."""

    generated_at_iso: str
    market_key: str
    title: str
    venue_yes: str
    venue_no: str
    net_edge_per_pair: float
    contracts: int
    capital_required_usd: float
    net_profit_usd: float
    verified: bool


def build_clob_token_map(
    poly_payloads: list[dict[str, Any]],
) -> dict[str, tuple[str, str]]:
    """Map a Polymarket market key -> (yes_token_id, no_token_id) from payloads."""
    out: dict[str, tuple[str, str]] = {}
    for payload in poly_payloads:
        key = _poly_key(payload)
        tokens = _parse_token_ids(payload.get("clobTokenIds"))
        if key and len(tokens) >= 2:
            out[key] = (tokens[0], tokens[1])
    return out


def refine_pair_with_depth(
    match: MatchedMarket,
    *,
    config: DetectorConfig,
    poly_tokens: dict[str, tuple[str, str]],
    fetch_fillable: FillableFetcher,
) -> ArbEvaluation:
    """Re-evaluate a matched pair using real Polymarket fill depth.

    Replaces the assumed Polymarket size with the CLOB-fillable size at the
    relevant ask price for each outcome, then re-runs the detector. The Kalshi
    leg keeps its top-of-book ask size from the market payload.
    """
    quote_a, quote_b = match.quote_a, match.quote_b
    poly_quote = quote_a if quote_a.venue == "polymarket" else (
        quote_b if quote_b.venue == "polymarket" else None
    )
    if poly_quote is None or poly_quote.market_key not in poly_tokens:
        return evaluate_market_pair(
            quote_a, quote_b, config=config,
            market_key=match.market_key, title=match.title,
        )

    yes_token, no_token = poly_tokens[poly_quote.market_key]
    yes_fill = fetch_fillable(yes_token, poly_quote.yes_ask)
    no_fill = fetch_fillable(no_token, poly_quote.no_ask)
    refined_poly = BinaryMarketQuote(
        venue=poly_quote.venue,
        market_key=poly_quote.market_key,
        title=poly_quote.title,
        yes_ask=poly_quote.yes_ask,
        no_ask=poly_quote.no_ask,
        yes_size=yes_fill if yes_fill is not None else poly_quote.yes_size,
        no_size=no_fill if no_fill is not None else poly_quote.no_size,
        event_time_ns=poly_quote.event_time_ns,
    )
    new_a = refined_poly if quote_a.venue == "polymarket" else quote_a
    new_b = refined_poly if quote_b.venue == "polymarket" else quote_b
    return evaluate_market_pair(
        new_a, new_b, config=config,
        market_key=match.market_key, title=match.title,
    )


def alerts_from_evaluations(
    evaluations: list[ArbEvaluation],
    *,
    verified_keys: set[str],
    generated_at: datetime | None = None,
    include_near_miss: bool = False,
) -> list[Alert]:
    """Shape actionable (and optionally near-miss) evaluations into alerts."""
    stamp = (generated_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    alerts: list[Alert] = []
    for ev in evaluations:
        surfaced = ev.is_actionable or (
            include_near_miss and ev.reason_code == REASON_PROFIT_BELOW_MINIMUM
        )
        if not surfaced:
            continue
        alerts.append(
            Alert(
                generated_at_iso=stamp,
                market_key=ev.market_key,
                title=ev.title,
                venue_yes=ev.venue_yes,
                venue_no=ev.venue_no,
                net_edge_per_pair=round(ev.net_edge_per_pair, 6),
                contracts=ev.contracts,
                capital_required_usd=round(ev.capital_required_usd, 6),
                net_profit_usd=round(ev.net_profit_usd, 6),
                verified=ev.market_key.split("|", 1)[0] in verified_keys,
            )
        )
    alerts.sort(key=lambda a: (-int(a.verified), -a.net_profit_usd))
    return alerts


def append_alerts(alerts: list[Alert], *, path: Path) -> None:
    """Append alerts as JSONL (one object per line) to the alert log."""
    if not alerts:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for alert in alerts:
            handle.write(json.dumps(asdict(alert), sort_keys=True) + "\n")


def format_alert(alert: Alert) -> str:
    tag = "✅VERIFIED" if alert.verified else "⚠️UNVERIFIED"
    return (
        f"[{tag}] {alert.title[:50]} | buy YES@{alert.venue_yes} NO@{alert.venue_no} "
        f"| edge {alert.net_edge_per_pair:+.3f} x{alert.contracts} "
        f"-> ${alert.net_profit_usd:.2f} on ${alert.capital_required_usd:.2f}"
    )


@dataclass(frozen=True)
class LivePassResult:
    matched: int
    evaluated: int
    alerts: list[Alert]


def run_live_once(
    *,
    config: DetectorConfig,
    watchlist_entries: list[Any],
    min_similarity: float,
    refine_top_n: int,
    alert_log: Path,
    include_near_miss: bool = True,
) -> LivePassResult:  # pragma: no cover - network orchestration
    """One live fetch -> match -> depth-refine -> alert pass."""
    from joint_research.predmarket_arb.depth import polymarket_fillable_size
    from joint_research.predmarket_arb.kalshi_client import (
        fetch_kalshi_markets,
        project_kalshi_markets,
    )
    from joint_research.predmarket_arb.matcher import match_markets
    from joint_research.predmarket_arb.polymarket_quotes import (
        fetch_polymarket_markets,
        project_polymarket_markets,
    )
    from joint_research.predmarket_arb.watchlist import verified_manual_map

    ns = int(datetime.now(UTC).timestamp() * 1_000_000_000)
    kal_payloads = fetch_kalshi_markets()
    poly_payloads = fetch_polymarket_markets()
    quotes_a = project_kalshi_markets(kal_payloads, event_time_ns=ns)
    quotes_b = project_polymarket_markets(poly_payloads, event_time_ns=ns)

    vmap = verified_manual_map(watchlist_entries)
    matches = match_markets(
        quotes_a, quotes_b, manual_map=vmap, min_similarity=min_similarity
    )
    token_map = build_clob_token_map(poly_payloads)

    # Rank by gross edge so the limited depth-refinement budget is spent on the
    # most promising candidates.
    ranked = sorted(
        matches,
        key=lambda m: -(1.0 - (m.quote_a.yes_ask + m.quote_b.no_ask)),
    )
    refine_keys = {m.market_key for m in ranked[:refine_top_n]}

    import httpx

    evaluations: list[ArbEvaluation] = []
    with httpx.Client(timeout=8.0) as book_client:
        def fetch_fillable(token: str, price: float) -> int | None:
            return polymarket_fillable_size(token, max_price=price, client=book_client)

        for match in matches:
            if match.market_key in refine_keys:
                evaluations.append(
                    refine_pair_with_depth(
                        match,
                        config=config,
                        poly_tokens=token_map,
                        fetch_fillable=fetch_fillable,
                    )
                )
            else:
                evaluations.append(
                    evaluate_market_pair(
                        match.quote_a, match.quote_b, config=config,
                        market_key=match.market_key, title=match.title,
                    )
                )

    alerts = alerts_from_evaluations(
        evaluations,
        verified_keys=set(vmap),
        include_near_miss=include_near_miss,
    )
    append_alerts(alerts, path=alert_log)
    return LivePassResult(matched=len(matches), evaluated=len(evaluations), alerts=alerts)


def _poly_key(payload: dict[str, Any]) -> str | None:
    for key in ("conditionId", "id", "slug"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_token_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [str(v) for v in decoded]
    return []
