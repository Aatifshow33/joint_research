"""Memory layer: structured store of decisions, outcomes, and calibrations.

Backed by Parquet so it's the same storage discipline as the warehouse.
Reviewers write to it; downstream runs read from it to inform priors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


MEMORY_PARQUET_NAME = "memory.parquet"


@dataclass
class AgentMemory:
    """Append-only Parquet log of agent decisions + postmortems."""

    root: Path

    def append(self, *, kind: str, run_id: str, payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        record = {
            "kind": kind,
            "run_id": run_id,
            "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        }
        table = pa.table({k: [v] for k, v in record.items()})
        # Append by writing a new shard so we never read-modify-write.
        shard = self.root / f"{kind}-{run_id}.parquet"
        pq.write_table(table, shard, compression="zstd", compression_level=3)
        return shard

    def read_all(self) -> pa.Table | None:
        files = sorted(self.root.glob("*.parquet"))
        if not files:
            return None
        tables = [pq.read_table(f) for f in files]
        return pa.concat_tables(tables, promote_options="default")
