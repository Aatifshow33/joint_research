"""Filesystem layout for the warehouse.

Layout:
    {root}/{table_name}/ingest_date=YYYY-MM-DD/{ingest_time_ns}-{shard}.parquet

We never overwrite. Every ingestion run writes a new shard file. DuckDB views
read the whole table directory; deduplication happens at query time on
``payload_hash``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_WAREHOUSE_ENV_VAR = "JOINT_RESEARCH_WAREHOUSE_ROOT"
DEFAULT_WAREHOUSE_REL_PATH = "data/warehouse"


@dataclass(frozen=True)
class WarehousePaths:
    root: Path

    @classmethod
    def from_env(cls, *, project_root: Path | None = None) -> WarehousePaths:
        env_root = os.environ.get(DEFAULT_WAREHOUSE_ENV_VAR)
        if env_root:
            return cls(root=Path(env_root).resolve())
        base = project_root if project_root is not None else Path.cwd()
        return cls(root=(base / DEFAULT_WAREHOUSE_REL_PATH).resolve())

    def table_dir(self, table_name: str) -> Path:
        return self.root / table_name

    def partition_dir(self, table_name: str, ingest_time_ns: int) -> Path:
        ingest_date = _ingest_date_from_ns(ingest_time_ns)
        return self.table_dir(table_name) / f"ingest_date={ingest_date}"

    def shard_path(
        self,
        *,
        table_name: str,
        ingest_time_ns: int,
        shard: str,
    ) -> Path:
        return self.partition_dir(table_name, ingest_time_ns) / f"{ingest_time_ns}-{shard}.parquet"


def _ingest_date_from_ns(ingest_time_ns: int) -> str:
    seconds, _ = divmod(ingest_time_ns, 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d")
