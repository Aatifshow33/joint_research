from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from joint_research.warehouse import (
    POLYMARKET_GAMMA_EVENTS,
    ParquetWriter,
    WarehousePaths,
)


def _row(payload_hash: str, event_id: str = "evt_1", event_time_ns: int = 1_700_000_000_000_000_000) -> dict[str, object]:
    return {
        "event_time_ns": event_time_ns,
        "source": "gamma.events",
        "payload_hash": payload_hash,
        "payload_json": '{"id":"' + event_id + '"}',
        "event_id": event_id,
        "slug": None,
        "title": None,
        "category": None,
        "active": None,
        "closed": None,
        "archived": None,
        "start_date_iso": None,
        "end_date_iso": None,
        "volume_usd": None,
        "liquidity_usd": None,
        "market_count": None,
    }


def test_write_creates_partitioned_parquet_file(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)

    out = writer.write([_row(payload_hash="abc")])

    assert out.exists()
    assert out.parent.parent == paths.table_dir(POLYMARKET_GAMMA_EVENTS.name)
    assert out.parent.name.startswith("ingest_date=")

    # Read without partition discovery so the file's own columns are tested.
    table = pq.read_table(out, partitioning=None)
    assert table.num_rows == 1
    declared_names = [f.name for f in POLYMARKET_GAMMA_EVENTS.schema]
    assert table.schema.names == declared_names
    assert table.column("payload_hash").to_pylist() == ["abc"]
    # ingest_time_ns is stamped by the writer, must be populated
    assert table.column("ingest_time_ns").to_pylist()[0] > 0


def test_two_writes_produce_two_shards(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)

    out_a = writer.write([_row(payload_hash="a")])
    out_b = writer.write([_row(payload_hash="b")])

    assert out_a != out_b
    table_dir = paths.table_dir(POLYMARKET_GAMMA_EVENTS.name)
    shards = list(table_dir.rglob("*.parquet"))
    assert len(shards) == 2


def test_empty_rows_rejected(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)

    with pytest.raises(ValueError, match="no_rows_to_write"):
        writer.write([])


def test_missing_required_column_rejected(tmp_path: Path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)

    bad_row = _row(payload_hash="x")
    del bad_row["event_id"]  # event_id is non-nullable

    with pytest.raises(ValueError, match="missing_required_column"):
        writer.write([bad_row])
