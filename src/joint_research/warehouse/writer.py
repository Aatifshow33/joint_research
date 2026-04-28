"""Append-only Parquet writer.

A writer is bound to one ``TableSchema``. Each ``write()`` call produces one
new shard file under the table's date partition. We never read+rewrite
existing files — duplicate keys are deduplicated at query time using the
``payload_hash`` column. This keeps writes cheap and concurrent ingestion
safe.
"""

from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.schema import TableSchema


class ParquetWriter:
    def __init__(self, *, table: TableSchema, paths: WarehousePaths) -> None:
        self._table = table
        self._paths = paths

    @property
    def table_name(self) -> str:
        return self._table.name

    def write(self, rows: Iterable[dict[str, object]]) -> Path:
        rows_list = list(rows)
        if not rows_list:
            raise ValueError(f"no_rows_to_write:table={self._table.name}")

        ingest_time_ns = time.time_ns()
        record_batch = self._build_batch(rows_list, ingest_time_ns=ingest_time_ns)
        out_table = pa.Table.from_batches([record_batch], schema=self._table.schema)
        self._table.validate_table(out_table)

        shard = secrets.token_hex(4)
        out_path = self._paths.shard_path(
            table_name=self._table.name,
            ingest_time_ns=ingest_time_ns,
            shard=shard,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        pq.write_table(
            out_table,
            out_path,
            compression="zstd",
            compression_level=3,
            use_dictionary=True,
        )
        return out_path

    def _build_batch(
        self,
        rows: list[dict[str, object]],
        *,
        ingest_time_ns: int,
    ) -> pa.RecordBatch:
        columns: dict[str, list[object]] = {field.name: [] for field in self._table.schema}
        for row in rows:
            for field in self._table.schema:
                if field.name == "ingest_time_ns":
                    columns[field.name].append(ingest_time_ns)
                    continue
                if field.name not in row:
                    if field.nullable:
                        columns[field.name].append(None)
                        continue
                    raise ValueError(
                        f"missing_required_column:table={self._table.name}:column={field.name}"
                    )
                columns[field.name].append(row[field.name])
        arrays = [
            pa.array(columns[field.name], type=field.type) for field in self._table.schema
        ]
        return pa.RecordBatch.from_arrays(arrays, schema=self._table.schema)
