"""Orchestrate one cross-venue arbitrage detection pass and write artifacts.

A scan takes two lists of normalized quotes (one per venue), matches markets,
evaluates each matched pair under a fee-aware detector, and produces a ranked
result plus warehouse-style artifacts. It deliberately keeps *every* evaluated
pair, actionable or not, so the artifacts answer the research question: how
often do real spreads clear the fee hurdle, and by how much do the near-misses
miss?
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from joint_research.predmarket_arb.detector import (
    ArbEvaluation,
    DetectorConfig,
    evaluate_market_pair,
)
from joint_research.predmarket_arb.fees import VenueFeeModel
from joint_research.predmarket_arb.matcher import (
    DEFAULT_MIN_SIMILARITY,
    MatchedMarket,
    match_markets,
)
from joint_research.predmarket_arb.types import BinaryMarketQuote

DEFAULT_ARTIFACT_SUBDIR = "research/predmarket_arb"


@dataclass(frozen=True)
class ScanRow:
    """One evaluated, matched market pair flattened for reporting."""

    market_key: str
    title: str
    similarity: float
    match_method: str
    venue_yes: str
    venue_no: str
    direction: str
    yes_ask: float
    no_ask: float
    gross_edge_per_pair: float
    fee_per_pair: float
    net_edge_per_pair: float
    contracts: int
    capital_required_usd: float
    net_profit_usd: float
    is_actionable: bool
    reason_code: str


@dataclass(frozen=True)
class ScanResult:
    """The full outcome of one detection pass."""

    generated_at_iso: str
    quotes_a_count: int
    quotes_b_count: int
    matched_count: int
    actionable_count: int
    total_actionable_profit_usd: float
    reason_counts: dict[str, int]
    rows: list[ScanRow]

    @property
    def actionable_rows(self) -> list[ScanRow]:
        return [row for row in self.rows if row.is_actionable]


def run_scan(
    quotes_a: list[BinaryMarketQuote],
    quotes_b: list[BinaryMarketQuote],
    *,
    config: DetectorConfig | None = None,
    fee_models: dict[str, VenueFeeModel] | None = None,
    manual_map: dict[str, str] | None = None,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    generated_at: datetime | None = None,
) -> ScanResult:
    """Match, evaluate, and rank one cross-venue scan."""

    cfg = config or DetectorConfig()
    matches = match_markets(
        quotes_a,
        quotes_b,
        manual_map=manual_map,
        min_similarity=min_similarity,
    )

    rows: list[ScanRow] = []
    for match in matches:
        evaluation = evaluate_market_pair(
            match.quote_a,
            match.quote_b,
            config=cfg,
            fee_models=fee_models,
            market_key=match.market_key,
            title=match.title,
        )
        rows.append(_to_scan_row(match, evaluation))

    rows.sort(key=lambda row: (-row.net_edge_per_pair, row.market_key))

    reason_counts = Counter(row.reason_code for row in rows)
    actionable = [row for row in rows if row.is_actionable]
    total_profit = sum(row.net_profit_usd for row in actionable)
    stamp = (generated_at or datetime.now(UTC)).astimezone(UTC)

    return ScanResult(
        generated_at_iso=stamp.isoformat(),
        quotes_a_count=len(quotes_a),
        quotes_b_count=len(quotes_b),
        matched_count=len(matches),
        actionable_count=len(actionable),
        total_actionable_profit_usd=round(total_profit, 6),
        reason_counts=dict(sorted(reason_counts.items())),
        rows=rows,
    )


def write_scan_artifacts(result: ScanResult, *, artifact_dir: Path) -> dict[str, Path]:
    """Write JSON, CSV, and Markdown artifacts; return the written paths."""

    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / "predmarket_arb_scan.json"
    csv_path = artifact_dir / "predmarket_arb_scan.csv"
    md_path = artifact_dir / "predmarket_arb_summary.md"

    json_path.write_text(_render_json(result), encoding="utf-8")
    _write_csv(csv_path, result)
    md_path.write_text(_render_markdown(result), encoding="utf-8")

    return {"json": json_path, "csv": csv_path, "markdown": md_path}


def _to_scan_row(match: MatchedMarket, evaluation: ArbEvaluation) -> ScanRow:
    return ScanRow(
        market_key=evaluation.market_key,
        title=evaluation.title,
        similarity=round(match.similarity, 6),
        match_method=match.match_method,
        venue_yes=evaluation.venue_yes,
        venue_no=evaluation.venue_no,
        direction=evaluation.direction,
        yes_ask=evaluation.yes_ask,
        no_ask=evaluation.no_ask,
        gross_edge_per_pair=round(evaluation.gross_edge_per_pair, 6),
        fee_per_pair=round(evaluation.fee_per_pair, 6),
        net_edge_per_pair=round(evaluation.net_edge_per_pair, 6),
        contracts=evaluation.contracts,
        capital_required_usd=round(evaluation.capital_required_usd, 6),
        net_profit_usd=round(evaluation.net_profit_usd, 6),
        is_actionable=evaluation.is_actionable,
        reason_code=evaluation.reason_code,
    )


def _render_json(result: ScanResult) -> str:
    payload = {
        "generated_at_iso": result.generated_at_iso,
        "quotes_a_count": result.quotes_a_count,
        "quotes_b_count": result.quotes_b_count,
        "matched_count": result.matched_count,
        "actionable_count": result.actionable_count,
        "total_actionable_profit_usd": result.total_actionable_profit_usd,
        "reason_counts": result.reason_counts,
        "rows": [asdict(row) for row in result.rows],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_csv(path: Path, result: ScanResult) -> None:
    fieldnames = list(ScanRow.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in result.rows:
            writer.writerow(asdict(row))


def _render_markdown(result: ScanResult) -> str:
    lines = [
        "# Cross-Venue Prediction-Market Arbitrage Scan",
        "",
        "> Research / detection artifact. No orders are placed. Edges are net of",
        "> modeled venue fees; near-misses are retained on purpose.",
        "",
        f"- generated_at: `{result.generated_at_iso}`",
        f"- venue A quotes: {result.quotes_a_count}",
        f"- venue B quotes: {result.quotes_b_count}",
        f"- matched markets: {result.matched_count}",
        f"- **actionable opportunities: {result.actionable_count}**",
        f"- total actionable net profit (modeled): "
        f"${result.total_actionable_profit_usd:.2f}",
        "",
        "## Outcome reason codes",
        "",
        "| reason_code | count |",
        "| --- | ---: |",
    ]
    for reason, count in result.reason_counts.items():
        lines.append(f"| {reason} | {count} |")

    lines += [
        "",
        "## Top opportunities by net edge per pair",
        "",
        "| market_key | net_edge/pair | contracts | capital | net_profit | "
        "reason |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in result.rows[:15]:
        lines.append(
            f"| {row.market_key} | {row.net_edge_per_pair:.4f} | {row.contracts} | "
            f"${row.capital_required_usd:.2f} | ${row.net_profit_usd:.2f} | "
            f"{row.reason_code} |"
        )
    lines.append("")
    return "\n".join(lines)
