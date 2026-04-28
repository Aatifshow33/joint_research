"""Drivers that compose Gamma+CLOB into warehouse writes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import duckdb

from joint_research.ingest.clob_prices_history import (
    fetch_prices_history,
    project_history_samples,
)
from joint_research.ingest.gamma_crypto_markets import (
    fetch_crypto_markets,
    project_gamma_market_payloads,
)
from joint_research.warehouse import (
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_PRICE_HISTORY,
    ParquetWriter,
    WarehousePaths,
)
from joint_research.warehouse.views import register_views


@dataclass(frozen=True)
class CryptoMarketsIngestResult:
    rows_written: int
    shard_path: str


@dataclass(frozen=True)
class PriceHistoryIngestResult:
    tokens_attempted: int
    tokens_with_data: int
    rows_written: int
    shard_path: str


async def ingest_gamma_crypto_markets(
    *,
    paths: WarehousePaths,
    limit: int = 500,
    active: bool = True,
    closed: bool = False,
) -> CryptoMarketsIngestResult:
    raw = await fetch_crypto_markets(limit=limit, active=active, closed=closed)
    fetched = datetime.now(tz=timezone.utc)
    rows = project_gamma_market_payloads(raw, fetched_at=fetched)
    if not rows:
        return CryptoMarketsIngestResult(rows_written=0, shard_path="")

    writer = ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return CryptoMarketsIngestResult(rows_written=len(rows), shard_path=str(shard))


async def ingest_top_crypto_market_prices(
    *,
    paths: WarehousePaths,
    top_n: int = 10,
    interval: str = "1m",
    fidelity_minutes: int = 60,
    inter_request_sleep_s: float = 0.1,
    include_closed: bool = False,
) -> PriceHistoryIngestResult:
    """Pick the top-N crypto markets by 1mo volume and pull each YES token's history.

    Reads from the warehouse via DuckDB so we honour whatever crypto markets
    have already been ingested rather than re-fetching from Gamma.

    Set ``include_closed=True`` to also pull resolved markets — required for
    survivorship-bias-free pattern discovery.
    """

    selected = _select_top_yes_tokens(paths=paths, top_n=top_n, include_closed=include_closed)
    if not selected:
        return PriceHistoryIngestResult(
            tokens_attempted=0, tokens_with_data=0, rows_written=0, shard_path=""
        )

    rows_to_write: list[dict[str, object]] = []
    tokens_with_data = 0
    async with __import__("httpx").AsyncClient(timeout=30.0) as client:
        for entry in selected:
            samples = await fetch_prices_history(
                token_id=entry.yes_token_id,
                interval=interval,
                fidelity_minutes=fidelity_minutes,
                client=client,
            )
            projected = project_history_samples(
                samples,
                token_id=entry.yes_token_id,
                market_id=entry.market_id,
                outcome="Yes",
                interval_label=interval,
                fidelity_minutes=fidelity_minutes,
            )
            if projected:
                tokens_with_data += 1
                rows_to_write.extend(r.to_warehouse_row() for r in projected)
            if inter_request_sleep_s > 0:
                await asyncio.sleep(inter_request_sleep_s)

    if not rows_to_write:
        return PriceHistoryIngestResult(
            tokens_attempted=len(selected),
            tokens_with_data=0,
            rows_written=0,
            shard_path="",
        )

    writer = ParquetWriter(table=POLYMARKET_PRICE_HISTORY, paths=paths)
    shard = writer.write(rows_to_write)
    return PriceHistoryIngestResult(
        tokens_attempted=len(selected),
        tokens_with_data=tokens_with_data,
        rows_written=len(rows_to_write),
        shard_path=str(shard),
    )


@dataclass(frozen=True)
class _TokenSelection:
    market_id: str
    yes_token_id: str
    question: str | None
    crypto_asset_tag: str | None


def _select_top_yes_tokens(
    *,
    paths: WarehousePaths,
    top_n: int,
    include_closed: bool,
) -> list[_TokenSelection]:
    con = duckdb.connect()
    register_views(con, paths)
    # Use volume_total_usd for ranking when including closed markets, since
    # 1-month volumes are zero for already-resolved markets.
    rank_expr = "coalesce(volume_total_usd, volume_1mo_usd, 0.0)" if include_closed else (
        "coalesce(volume_1mo_usd, volume_total_usd, 0.0)"
    )
    active_filter = "" if include_closed else "AND coalesce(active, true)"
    query = f"""
        SELECT market_id, yes_token_id, question, crypto_asset_tag,
               {rank_expr} AS rank_volume
        FROM polymarket_crypto_markets
        WHERE yes_token_id IS NOT NULL
          {active_filter}
        ORDER BY rank_volume DESC
        LIMIT ?
    """
    rows = con.execute(query, [top_n]).fetchall()
    return [
        _TokenSelection(
            market_id=row[0],
            yes_token_id=row[1],
            question=row[2],
            crypto_asset_tag=row[3],
        )
        for row in rows
    ]
