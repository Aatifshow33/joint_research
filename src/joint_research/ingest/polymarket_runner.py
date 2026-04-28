"""Wire ``polymarket_arb.clients.gamma.GammaClient`` to the warehouse writer.

Kept in its own module so the projection logic in ``polymarket_gamma`` stays
testable without depending on the live HTTP client.
"""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.ingest.polymarket_gamma import (
    GammaEventRow,
    project_gamma_event_payload,
)
from joint_research.warehouse import POLYMARKET_GAMMA_EVENTS, ParquetWriter, WarehousePaths


@dataclass(frozen=True)
class GammaIngestResult:
    rows_written: int
    shard_path: str


async def ingest_gamma_events(
    *,
    paths: WarehousePaths,
    limit: int = 500,
    active: bool = True,
    closed: bool = False,
    archived: bool = False,
) -> GammaIngestResult:
    """Fetch one page of Gamma events and write them as a single shard.

    Imports ``polymarket_arb`` lazily so this package can be tested in
    isolation when the sibling repo isn't on ``sys.path``.
    """

    from polymarket_arb.clients.gamma import GammaClient  # noqa: PLC0415
    from polymarket_arb.config import Settings  # noqa: PLC0415

    settings = Settings()
    client = GammaClient(settings)
    try:
        raw_events = await client.list_events(
            limit=limit,
            active=active,
            closed=closed,
            archived=archived,
        )
    finally:
        await client.aclose()

    rows: list[GammaEventRow] = [
        project_gamma_event_payload(event.payload, fetched_at=event.fetched_at)
        for event in raw_events
    ]
    if not rows:
        return GammaIngestResult(rows_written=0, shard_path="")

    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return GammaIngestResult(rows_written=len(rows), shard_path=str(shard))
