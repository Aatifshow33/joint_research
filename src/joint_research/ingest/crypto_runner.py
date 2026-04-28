"""Driver that pulls Binance klines for a window and writes to the warehouse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from joint_research.ingest.binance_klines import (
    fetch_binance_klines_paged,
    project_binance_klines,
)
from joint_research.warehouse import CRYPTO_OHLCV, ParquetWriter, WarehousePaths


@dataclass(frozen=True)
class CryptoOhlcvIngestResult:
    rows_written: int
    shard_path: str
    symbol: str
    interval: str
    start_iso: str
    end_iso: str


async def ingest_binance_ohlcv(
    *,
    paths: WarehousePaths,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> CryptoOhlcvIngestResult:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start_and_end_must_be_timezone_aware")
    start_ms = int(start.astimezone(timezone.utc).timestamp() * 1000)
    end_ms = int(end.astimezone(timezone.utc).timestamp() * 1000)

    raw_klines = await fetch_binance_klines_paged(
        symbol=symbol,
        interval=interval,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
    )
    rows = project_binance_klines(raw_klines, symbol=symbol, interval=interval)
    if not rows:
        return CryptoOhlcvIngestResult(
            rows_written=0,
            shard_path="",
            symbol=symbol.upper(),
            interval=interval,
            start_iso=start.isoformat(),
            end_iso=end.isoformat(),
        )

    writer = ParquetWriter(table=CRYPTO_OHLCV, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return CryptoOhlcvIngestResult(
        rows_written=len(rows),
        shard_path=str(shard),
        symbol=symbol.upper(),
        interval=interval,
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
    )
