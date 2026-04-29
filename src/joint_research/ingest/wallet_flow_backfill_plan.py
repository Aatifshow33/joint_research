"""Staged wallet-flow backfill planning and optional execution."""

from __future__ import annotations

import asyncio
import csv
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from joint_research.ingest.polymarket_wallet_flow import WalletFlowIngestResult
from joint_research.warehouse import WarehousePaths, register_views

STAGE_1_QUICK = "stage_1_quick"
STAGE_2_DEPTH = "stage_2_depth"
STAGE_3_BREADTH = "stage_3_breadth"

STAGE_ORDER: tuple[str, ...] = (
    STAGE_1_QUICK,
    STAGE_2_DEPTH,
    STAGE_3_BREADTH,
)
STAGE_DEFAULT_LIMITS: dict[str, int] = {
    STAGE_1_QUICK: 50,
    STAGE_2_DEPTH: 150,
    STAGE_3_BREADTH: 300,
}


@dataclass(frozen=True)
class MarketCoverageRow:
    market_id: str
    market_slug: str | None
    asset: str
    is_active: bool
    is_closed: bool
    is_archived: bool
    volume_1mo_usd: float
    volume_total_usd: float
    wallet_flow_rows: int
    trade_rows: int
    copy_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int


@dataclass(frozen=True)
class BackfillPlanRow:
    stage: str
    stage_rank: int
    market_id: str
    market_slug: str | None
    asset: str
    volume_1mo_usd: float
    volume_total_usd: float
    wallet_flow_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int
    undercovered: bool
    selection_reason: str


@dataclass(frozen=True)
class CoverageSummary:
    markets_total: int
    markets_with_wallet_flow: int
    wallet_flow_rows: int
    trade_rows: int
    copy_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int


@dataclass(frozen=True)
class BackfillPlanArtifacts:
    plan_md: Path
    plan_csv: Path
    coverage_csv: Path


@dataclass(frozen=True)
class BackfillExecutionSummary:
    stage: str
    rows_written: int
    trade_rows_written: int
    copy_rows_written: int
    markets_scanned: int
    markets_with_rows: int
    skipped_markets: int
    source_clients: tuple[str, ...]
    warnings: tuple[str, ...]
    before: CoverageSummary
    after: CoverageSummary


@dataclass(frozen=True)
class BackfillPlanResult:
    artifacts: BackfillPlanArtifacts
    selected_stage: str
    selected_stage_markets: int
    stage_counts: dict[str, int]
    before: CoverageSummary
    execution: BackfillExecutionSummary | None


def run_wallet_flow_backfill_plan(
    *,
    paths: WarehousePaths,
    output_dir: Path,
    asset: str = "ALL",
    stage: str = STAGE_1_QUICK,
    limit_markets: int | None = None,
    limit_events: int = 2000,
    min_volume: float = 0.0,
    execute: bool = False,
    dry_run: bool = True,
    ingest_runner: Callable[..., Awaitable[WalletFlowIngestResult]] | None = None,
) -> BackfillPlanResult:
    if stage not in STAGE_ORDER:
        raise ValueError(f"unsupported_stage:{stage}")

    asset_filter = _normalize_asset(asset)
    coverage_rows = load_market_coverage(paths=paths)
    before_summary = summarize_coverage(coverage_rows)
    staged = build_backfill_plan(
        coverage_rows,
        asset=asset_filter,
        min_volume=min_volume,
        limit_markets=limit_markets,
    )
    artifacts = write_backfill_plan_artifacts(
        output_dir=output_dir,
        coverage_rows=coverage_rows,
        staged_plan=staged,
        selected_stage=stage,
        before=before_summary,
        dry_run=(dry_run and not execute),
    )

    execution: BackfillExecutionSummary | None = None
    if execute:
        runner = ingest_runner or _default_ingest_runner
        selected_rows = staged.get(stage, [])
        result = asyncio.run(
            runner(
                paths=paths,
                limit_markets=len(selected_rows),
                limit_events=max(limit_events, 0),
                min_volume=max(min_volume, 0.0),
                asset=None if asset_filter == "ALL" else asset_filter,
                lookback_hours=None,
                large_trade_usdc=1_000.0,
                include_copy_signals=True,
            )
        )
        after_summary = summarize_coverage(load_market_coverage(paths=paths))
        execution = BackfillExecutionSummary(
            stage=stage,
            rows_written=result.rows_written,
            trade_rows_written=result.trade_rows,
            copy_rows_written=result.copy_rows,
            markets_scanned=result.markets_scanned,
            markets_with_rows=result.markets_with_rows,
            skipped_markets=result.skipped_markets,
            source_clients=result.source_clients,
            warnings=result.warnings,
            before=before_summary,
            after=after_summary,
        )

    return BackfillPlanResult(
        artifacts=artifacts,
        selected_stage=stage,
        selected_stage_markets=len(staged.get(stage, [])),
        stage_counts={name: len(rows) for name, rows in staged.items()},
        before=before_summary,
        execution=execution,
    )


def load_market_coverage(*, paths: WarehousePaths) -> list[MarketCoverageRow]:
    con = duckdb.connect()
    register_views(con, paths)
    rows = con.execute(
        """
        WITH latest_markets AS (
          SELECT * EXCLUDE (rn)
          FROM (
            SELECT
              market_id,
              slug AS market_slug,
              upper(crypto_asset_tag) AS asset,
              active,
              closed,
              archived,
              coalesce(volume_1mo_usd, 0) AS volume_1mo_usd,
              coalesce(volume_total_usd, 0) AS volume_total_usd,
              event_time_ns,
              ingest_time_ns,
              ROW_NUMBER() OVER (
                PARTITION BY market_id
                ORDER BY event_time_ns DESC, ingest_time_ns DESC
              ) AS rn
            FROM polymarket_crypto_markets
            WHERE market_id IS NOT NULL
              AND crypto_asset_tag IS NOT NULL
          )
          WHERE rn = 1
        ),
        wallet_agg AS (
          SELECT
            market_id,
            count(*) AS wallet_flow_rows,
            sum(CASE WHEN record_type = 'wallet_trade' THEN 1 ELSE 0 END) AS trade_rows,
            sum(CASE WHEN record_type = 'copy_event' THEN 1 ELSE 0 END) AS copy_rows
          FROM polymarket_wallet_flow
          WHERE market_id IS NOT NULL
          GROUP BY market_id
        ),
        flow_agg AS (
          SELECT market_id, count(*) AS market_flow_hourly_rows
          FROM polymarket_market_flow_hourly
          WHERE market_id IS NOT NULL
          GROUP BY market_id
        ),
        whale_agg AS (
          SELECT market_id, count(*) AS whale_flow_hourly_rows
          FROM polymarket_whale_flow_hourly
          WHERE market_id IS NOT NULL
          GROUP BY market_id
        )
        SELECT
          m.market_id,
          m.market_slug,
          m.asset,
          coalesce(m.active, false) AS is_active,
          coalesce(m.closed, false) AS is_closed,
          coalesce(m.archived, false) AS is_archived,
          m.volume_1mo_usd,
          m.volume_total_usd,
          coalesce(w.wallet_flow_rows, 0) AS wallet_flow_rows,
          coalesce(w.trade_rows, 0) AS trade_rows,
          coalesce(w.copy_rows, 0) AS copy_rows,
          coalesce(f.market_flow_hourly_rows, 0) AS market_flow_hourly_rows,
          coalesce(h.whale_flow_hourly_rows, 0) AS whale_flow_hourly_rows
        FROM latest_markets m
        LEFT JOIN wallet_agg w ON w.market_id = m.market_id
        LEFT JOIN flow_agg f ON f.market_id = m.market_id
        LEFT JOIN whale_agg h ON h.market_id = m.market_id
        ORDER BY m.market_id
        """
    ).fetchall()
    return [
        MarketCoverageRow(
            market_id=str(row[0]),
            market_slug=row[1],
            asset=str(row[2]).upper(),
            is_active=bool(row[3]),
            is_closed=bool(row[4]),
            is_archived=bool(row[5]),
            volume_1mo_usd=float(row[6] or 0.0),
            volume_total_usd=float(row[7] or 0.0),
            wallet_flow_rows=int(row[8] or 0),
            trade_rows=int(row[9] or 0),
            copy_rows=int(row[10] or 0),
            market_flow_hourly_rows=int(row[11] or 0),
            whale_flow_hourly_rows=int(row[12] or 0),
        )
        for row in rows
    ]


def summarize_coverage(rows: Sequence[MarketCoverageRow]) -> CoverageSummary:
    markets_with_wallet_flow = sum(1 for row in rows if row.wallet_flow_rows > 0)
    return CoverageSummary(
        markets_total=len(rows),
        markets_with_wallet_flow=markets_with_wallet_flow,
        wallet_flow_rows=sum(row.wallet_flow_rows for row in rows),
        trade_rows=sum(row.trade_rows for row in rows),
        copy_rows=sum(row.copy_rows for row in rows),
        market_flow_hourly_rows=sum(row.market_flow_hourly_rows for row in rows),
        whale_flow_hourly_rows=sum(row.whale_flow_hourly_rows for row in rows),
    )


def build_backfill_plan(
    coverage_rows: Sequence[MarketCoverageRow],
    *,
    asset: str,
    min_volume: float,
    limit_markets: int | None,
) -> dict[str, list[BackfillPlanRow]]:
    filtered_asset_rows = _filter_asset_rows(coverage_rows, asset=asset)
    rows = [
        row
        for row in filtered_asset_rows
        if max(row.volume_1mo_usd, row.volume_total_usd) >= max(min_volume, 0.0)
    ]

    stage_candidates: dict[str, list[MarketCoverageRow]] = {
        STAGE_1_QUICK: [row for row in rows if row.asset in {"BTC", "ETH"}],
        STAGE_2_DEPTH: rows,
        STAGE_3_BREADTH: rows,
    }

    planned: dict[str, list[BackfillPlanRow]] = {}
    for stage_name in STAGE_ORDER:
        candidates = sorted(stage_candidates[stage_name], key=_priority_sort_key)
        stage_limit = max(limit_markets or STAGE_DEFAULT_LIMITS[stage_name], 0)
        selected = candidates[:stage_limit]
        planned[stage_name] = [
            BackfillPlanRow(
                stage=stage_name,
                stage_rank=idx + 1,
                market_id=row.market_id,
                market_slug=row.market_slug,
                asset=row.asset,
                volume_1mo_usd=row.volume_1mo_usd,
                volume_total_usd=row.volume_total_usd,
                wallet_flow_rows=row.wallet_flow_rows,
                market_flow_hourly_rows=row.market_flow_hourly_rows,
                whale_flow_hourly_rows=row.whale_flow_hourly_rows,
                undercovered=_is_undercovered(row),
                selection_reason=_selection_reason(row),
            )
            for idx, row in enumerate(selected)
        ]
    return planned


def write_backfill_plan_artifacts(
    *,
    output_dir: Path,
    coverage_rows: Sequence[MarketCoverageRow],
    staged_plan: dict[str, list[BackfillPlanRow]],
    selected_stage: str,
    before: CoverageSummary,
    dry_run: bool,
) -> BackfillPlanArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_md = output_dir / "wallet_flow_backfill_plan.md"
    plan_csv = output_dir / "wallet_flow_backfill_plan.csv"
    coverage_csv = output_dir / "wallet_flow_coverage.csv"

    _write_coverage_csv(coverage_csv, coverage_rows)
    _write_plan_csv(plan_csv, staged_plan)
    plan_md.write_text(_render_plan_md(staged_plan=staged_plan, selected_stage=selected_stage, before=before, dry_run=dry_run))

    return BackfillPlanArtifacts(plan_md=plan_md, plan_csv=plan_csv, coverage_csv=coverage_csv)


def _write_coverage_csv(path: Path, rows: Sequence[MarketCoverageRow]) -> None:
    fieldnames = [
        "market_id",
        "market_slug",
        "asset",
        "is_active",
        "is_closed",
        "is_archived",
        "volume_1mo_usd",
        "volume_total_usd",
        "wallet_flow_rows",
        "trade_rows",
        "copy_rows",
        "market_flow_hourly_rows",
        "whale_flow_hourly_rows",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "market_id": row.market_id,
                    "market_slug": row.market_slug or "",
                    "asset": row.asset,
                    "is_active": row.is_active,
                    "is_closed": row.is_closed,
                    "is_archived": row.is_archived,
                    "volume_1mo_usd": row.volume_1mo_usd,
                    "volume_total_usd": row.volume_total_usd,
                    "wallet_flow_rows": row.wallet_flow_rows,
                    "trade_rows": row.trade_rows,
                    "copy_rows": row.copy_rows,
                    "market_flow_hourly_rows": row.market_flow_hourly_rows,
                    "whale_flow_hourly_rows": row.whale_flow_hourly_rows,
                }
            )


def _write_plan_csv(path: Path, staged_plan: dict[str, list[BackfillPlanRow]]) -> None:
    fieldnames = [
        "stage",
        "stage_rank",
        "market_id",
        "market_slug",
        "asset",
        "volume_1mo_usd",
        "volume_total_usd",
        "wallet_flow_rows",
        "market_flow_hourly_rows",
        "whale_flow_hourly_rows",
        "undercovered",
        "selection_reason",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for stage_name in STAGE_ORDER:
            for row in staged_plan.get(stage_name, []):
                writer.writerow(
                    {
                        "stage": row.stage,
                        "stage_rank": row.stage_rank,
                        "market_id": row.market_id,
                        "market_slug": row.market_slug or "",
                        "asset": row.asset,
                        "volume_1mo_usd": row.volume_1mo_usd,
                        "volume_total_usd": row.volume_total_usd,
                        "wallet_flow_rows": row.wallet_flow_rows,
                        "market_flow_hourly_rows": row.market_flow_hourly_rows,
                        "whale_flow_hourly_rows": row.whale_flow_hourly_rows,
                        "undercovered": row.undercovered,
                        "selection_reason": row.selection_reason,
                    }
                )


def _render_plan_md(
    *,
    staged_plan: dict[str, list[BackfillPlanRow]],
    selected_stage: str,
    before: CoverageSummary,
    dry_run: bool,
) -> str:
    lines = [
        "# Wallet Flow Backfill Plan",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        f"- Mode: {'dry-run' if dry_run else 'execute'}",
        f"- Selected stage: {selected_stage}",
        f"- Stage 1 markets: {len(staged_plan.get(STAGE_1_QUICK, []))}",
        f"- Stage 2 markets: {len(staged_plan.get(STAGE_2_DEPTH, []))}",
        f"- Stage 3 markets: {len(staged_plan.get(STAGE_3_BREADTH, []))}",
        "",
        "## Coverage Snapshot",
        "",
        f"- markets_total: {before.markets_total}",
        f"- markets_with_wallet_flow: {before.markets_with_wallet_flow}",
        f"- wallet_flow_rows: {before.wallet_flow_rows}",
        f"- trade_rows: {before.trade_rows}",
        f"- copy_rows: {before.copy_rows}",
        f"- market_flow_hourly_rows: {before.market_flow_hourly_rows}",
        f"- whale_flow_hourly_rows: {before.whale_flow_hourly_rows}",
        "",
        "## Staged Plan",
        "",
        f"- `{STAGE_1_QUICK}`: BTC/ETH-first quick coverage",
        f"- `{STAGE_2_DEPTH}`: deeper all-asset backfill",
        f"- `{STAGE_3_BREADTH}`: broadest market coverage",
        "",
        "## Top Selected Stage Markets",
        "",
    ]

    stage_rows = staged_plan.get(selected_stage, [])
    if not stage_rows:
        lines.append("No markets matched this stage/filter.")
        return "\n".join(lines) + "\n"

    lines.append("| Rank | Asset | Market | 1mo Vol | Wallet Rows | Flow Hours | Reason |")
    lines.append("| ---: | --- | --- | ---: | ---: | ---: | --- |")
    for row in stage_rows[:20]:
        market_label = row.market_slug or row.market_id
        lines.append(
            f"| {row.stage_rank} | {row.asset} | {market_label} | {row.volume_1mo_usd:.2f} | "
            f"{row.wallet_flow_rows} | {row.market_flow_hourly_rows} | {row.selection_reason} |"
        )
    return "\n".join(lines) + "\n"


def _normalize_asset(asset: str) -> str:
    cleaned = asset.strip().upper()
    return cleaned if cleaned else "ALL"


def _filter_asset_rows(rows: Sequence[MarketCoverageRow], *, asset: str) -> list[MarketCoverageRow]:
    if asset == "ALL":
        return list(rows)
    return [row for row in rows if row.asset == asset]


def _priority_sort_key(row: MarketCoverageRow) -> tuple[float, ...]:
    asset_priority = {
        "BTC": 0,
        "ETH": 1,
        "SOL": 2,
        "XRP": 3,
    }.get(row.asset, 4)
    active_priority = 0 if row.is_active and not row.is_closed and not row.is_archived else 1
    undercovered_priority = _undercoverage_bucket(row)
    volume = max(row.volume_1mo_usd, row.volume_total_usd)
    return (
        asset_priority,
        undercovered_priority,
        active_priority,
        -volume,
        row.wallet_flow_rows,
        row.market_flow_hourly_rows,
        row.market_id,
    )


def _undercoverage_bucket(row: MarketCoverageRow) -> int:
    if row.wallet_flow_rows == 0 or row.market_flow_hourly_rows == 0:
        return 0
    if row.wallet_flow_rows < 25 or row.market_flow_hourly_rows < 10:
        return 1
    if row.wallet_flow_rows < 100 or row.market_flow_hourly_rows < 24:
        return 2
    return 3


def _is_undercovered(row: MarketCoverageRow) -> bool:
    return _undercoverage_bucket(row) <= 1


def _selection_reason(row: MarketCoverageRow) -> str:
    reasons: list[str] = []
    if row.asset in {"BTC", "ETH"}:
        reasons.append("priority_asset")
    elif row.asset in {"SOL", "XRP"}:
        reasons.append("secondary_asset")
    else:
        reasons.append("other_asset")

    if row.is_active and not row.is_closed and not row.is_archived:
        reasons.append("active")
    if _is_undercovered(row):
        reasons.append("undercovered")

    if max(row.volume_1mo_usd, row.volume_total_usd) > 0:
        reasons.append("volume")
    return ",".join(reasons)


async def _default_ingest_runner(**kwargs) -> WalletFlowIngestResult:  # type: ignore[no-untyped-def]
    from joint_research.ingest.polymarket_wallet_flow import (  # noqa: PLC0415
        ingest_polymarket_wallet_flow,
    )

    return await ingest_polymarket_wallet_flow(**kwargs)
