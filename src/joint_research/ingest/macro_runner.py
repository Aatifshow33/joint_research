"""Driver: pull FRED macro series and write to warehouse."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.ingest.fred_macro import (
    fetch_fred_csv,
    project_fred_csv,
)
from joint_research.warehouse import MACRO_SERIES, ParquetWriter, WarehousePaths


@dataclass(frozen=True)
class MacroIngestResult:
    series_id: str
    rows_written: int
    shard_path: str


def ingest_fred_series(
    *,
    paths: WarehousePaths,
    series_id: str,
    units: str | None = None,
    frequency: str | None = None,
) -> MacroIngestResult:
    csv_text = fetch_fred_csv(series_id=series_id)
    rows = project_fred_csv(
        csv_text, series_id=series_id, units=units, frequency=frequency
    )
    if not rows:
        return MacroIngestResult(series_id=series_id.upper(), rows_written=0, shard_path="")
    writer = ParquetWriter(table=MACRO_SERIES, paths=paths)
    shard = writer.write([r.to_warehouse_row() for r in rows])
    return MacroIngestResult(
        series_id=series_id.upper(),
        rows_written=len(rows),
        shard_path=str(shard),
    )
