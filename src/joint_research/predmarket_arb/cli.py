"""``predmarket-arb`` CLI: run a cross-venue arbitrage detection scan.

Two input modes:

* ``--fixtures-dir DIR`` (offline): reads ``kalshi_markets.json`` and
  ``polymarket_markets.json`` — each a JSON list of raw venue payloads — and
  projects them through the same adapters used live. This is the default path
  for research and CI.
* ``--live`` (network): fetches open markets from both venues.

Either way the scan is deterministic given its inputs and writes JSON/CSV/MD
artifacts. No orders are ever placed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from joint_research.predmarket_arb.detector import DetectorConfig
from joint_research.predmarket_arb.kalshi_client import project_kalshi_markets
from joint_research.predmarket_arb.polymarket_quotes import project_polymarket_markets
from joint_research.predmarket_arb.scan import (
    DEFAULT_ARTIFACT_SUBDIR,
    ScanResult,
    run_scan,
    write_scan_artifacts,
)
from joint_research.predmarket_arb.types import BinaryMarketQuote

app = typer.Typer(help="Cross-venue prediction-market arbitrage detection (no execution).")

_REPO_ROOT = Path(__file__).resolve().parents[3]


@app.command()
def scan(
    fixtures_dir: Path | None = typer.Option(
        None,
        "--fixtures-dir",
        help="Directory with kalshi_markets.json and polymarket_markets.json.",
    ),
    live: bool = typer.Option(
        False, "--live", help="Fetch open markets from both venues over the network."
    ),
    bankroll: float = typer.Option(200.0, "--bankroll", help="Account size in USD."),
    min_edge: float = typer.Option(
        0.02, "--min-edge", help="Minimum net edge per $1 pair to count as actionable."
    ),
    min_profit: float = typer.Option(
        1.0, "--min-profit", help="Minimum modeled net profit (USD) to be actionable."
    ),
    min_similarity: float = typer.Option(
        0.6, "--min-similarity", help="Minimum title overlap to auto-match markets."
    ),
    manual_map_path: Path | None = typer.Option(
        None, "--manual-map", help="JSON {kalshi_key: polymarket_key} trusted links."
    ),
    artifact_dir: Path | None = typer.Option(
        None, "--artifact-dir", help="Where to write scan artifacts."
    ),
) -> None:
    """Run one detection scan and write artifacts."""

    event_time_ns = int(datetime.now(UTC).timestamp() * 1_000_000_000)

    if live and fixtures_dir is not None:
        raise typer.BadParameter("pass either --live or --fixtures-dir, not both")
    if live:
        quotes_a, quotes_b = _load_live_quotes(event_time_ns)
    elif fixtures_dir is not None:
        quotes_a, quotes_b = _load_fixture_quotes(fixtures_dir, event_time_ns)
    else:
        raise typer.BadParameter("provide --fixtures-dir or --live")

    config = DetectorConfig(
        bankroll_usd=bankroll,
        min_net_edge_per_pair=min_edge,
        min_net_profit_usd=min_profit,
    )
    manual_map = _load_manual_map(manual_map_path)

    result = run_scan(
        quotes_a,
        quotes_b,
        config=config,
        manual_map=manual_map,
        min_similarity=min_similarity,
    )

    target_dir = artifact_dir or (_REPO_ROOT / "artifacts" / DEFAULT_ARTIFACT_SUBDIR)
    paths = write_scan_artifacts(result, artifact_dir=target_dir)

    _print_summary(result, paths)


def _load_fixture_quotes(
    fixtures_dir: Path, event_time_ns: int
) -> tuple[list[BinaryMarketQuote], list[BinaryMarketQuote]]:
    kalshi_payloads = _load_json_list(fixtures_dir / "kalshi_markets.json")
    polymarket_payloads = _load_json_list(fixtures_dir / "polymarket_markets.json")
    quotes_a = project_kalshi_markets(kalshi_payloads, event_time_ns=event_time_ns)
    quotes_b = project_polymarket_markets(polymarket_payloads, event_time_ns=event_time_ns)
    return quotes_a, quotes_b


def _load_live_quotes(
    event_time_ns: int,
) -> tuple[list[BinaryMarketQuote], list[BinaryMarketQuote]]:  # pragma: no cover
    from joint_research.predmarket_arb.kalshi_client import fetch_kalshi_markets

    kalshi_payloads = fetch_kalshi_markets()
    quotes_a = project_kalshi_markets(kalshi_payloads, event_time_ns=event_time_ns)
    # Polymarket live fetch is intentionally left to the warehouse ingest path;
    # without it, the live scan runs Kalshi-only and reports zero matches rather
    # than guessing at an endpoint shape.
    quotes_b: list[BinaryMarketQuote] = []
    return quotes_a, quotes_b


def _load_manual_map(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("manual map must be a JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise typer.BadParameter(f"missing fixture: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise typer.BadParameter(f"fixture must be a JSON list: {path}")
    return [item for item in payload if isinstance(item, dict)]


def _print_summary(result: ScanResult, paths: dict[str, Path]) -> None:
    typer.echo(
        f"matched={result.matched_count} "
        f"actionable={result.actionable_count} "
        f"modeled_profit=${result.total_actionable_profit_usd:.2f}"
    )
    for reason, count in result.reason_counts.items():
        typer.echo(f"  {reason}: {count}")
    for label, path in paths.items():
        typer.echo(f"wrote {label}: {path}")


@app.command()
def version() -> None:
    """Print the detector contract version."""
    typer.echo("predmarket-arb detector v1 (detection only, no execution)")


if __name__ == "__main__":  # pragma: no cover
    app()
