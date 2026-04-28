"""Driver: pull whale wallet activity via polymarket-arb and write to warehouse."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.ingest.wallet_activity import project_wallet_activity_dump
from joint_research.warehouse import POLYMARKET_WALLET_ACTIVITY, ParquetWriter, WarehousePaths


@dataclass(frozen=True)
class WalletActivityIngestResult:
    wallets_selected: int
    activities_fetched: int
    rows_written: int
    shard_path: str


async def ingest_whale_wallet_activity(
    *,
    paths: WarehousePaths,
    limit: int = 50,
) -> WalletActivityIngestResult:
    """Discover top wallets via leaderboard + holders, fetch their activity.

    Defers to ``polymarket_arb.services.wallet_backfill_service.WalletBackfillService``
    so the Polymarket-side discovery logic stays in one place.
    """

    from polymarket_arb.config import Settings  # noqa: PLC0415
    from polymarket_arb.services.wallet_backfill_service import (  # noqa: PLC0415
        WalletBackfillService,
    )

    settings = Settings()
    service = WalletBackfillService(settings=settings)
    payload = await service.build_wallet_backfill(limit=limit)
    activities = payload.get("wallet_activities", [])

    rows: list = []
    for record in activities:
        try:
            rows.append(project_wallet_activity_dump(record))
        except ValueError:
            continue

    if not rows:
        return WalletActivityIngestResult(
            wallets_selected=len(payload.get("selected_wallets", [])),
            activities_fetched=len(activities),
            rows_written=0,
            shard_path="",
        )

    writer = ParquetWriter(table=POLYMARKET_WALLET_ACTIVITY, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return WalletActivityIngestResult(
        wallets_selected=len(payload.get("selected_wallets", [])),
        activities_fetched=len(activities),
        rows_written=len(rows),
        shard_path=str(shard),
    )
