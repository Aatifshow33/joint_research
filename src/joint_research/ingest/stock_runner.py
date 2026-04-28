"""Driver: pull stock OHLCV via yfinance and write to the warehouse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from joint_research.ingest.yfinance_stocks import project_yfinance_dataframe
from joint_research.warehouse import STOCK_OHLCV, ParquetWriter, WarehousePaths


@dataclass(frozen=True)
class StockOhlcvIngestResult:
    rows_written: int
    shard_path: str
    symbol: str
    interval: str
    start_iso: str
    end_iso: str


def ingest_yfinance_stock(
    *,
    paths: WarehousePaths,
    symbol: str,
    interval: str = "1d",
    start: datetime | None = None,
    end: datetime | None = None,
) -> StockOhlcvIngestResult:
    """Fetch ``symbol``'s history via yfinance and write a Parquet shard."""

    import yfinance as yf  # noqa: PLC0415  -- localized import

    if start is not None and start.tzinfo is None:
        raise ValueError("start must be timezone-aware UTC if provided")
    if end is not None and end.tzinfo is None:
        raise ValueError("end must be timezone-aware UTC if provided")

    # yfinance accepts naive ``YYYY-MM-DD`` strings; our schedule is UTC.
    start_str = start.astimezone(timezone.utc).strftime("%Y-%m-%d") if start else None
    end_str = end.astimezone(timezone.utc).strftime("%Y-%m-%d") if end else None

    ticker = yf.Ticker(symbol)
    df = ticker.history(
        start=start_str,
        end=end_str,
        interval=interval,
        auto_adjust=False,
        actions=True,
    )
    rows = project_yfinance_dataframe(df, symbol=symbol, interval=interval)
    if not rows:
        return StockOhlcvIngestResult(
            rows_written=0, shard_path="", symbol=symbol.upper(),
            interval=interval,
            start_iso=start.isoformat() if start else "",
            end_iso=end.isoformat() if end else "",
        )

    writer = ParquetWriter(table=STOCK_OHLCV, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return StockOhlcvIngestResult(
        rows_written=len(rows),
        shard_path=str(shard),
        symbol=symbol.upper(),
        interval=interval,
        start_iso=start.isoformat() if start else "",
        end_iso=end.isoformat() if end else "",
    )
