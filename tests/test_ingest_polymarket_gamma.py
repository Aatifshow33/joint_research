from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from joint_research.ingest.polymarket_gamma import (
    GAMMA_SOURCE,
    canonical_payload_hash,
    project_gamma_event_payload,
)
from joint_research.warehouse import POLYMARKET_GAMMA_EVENTS, ParquetWriter, WarehousePaths


def _fetched_at() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def test_projects_minimum_payload() -> None:
    payload = {"id": "evt-123"}

    row = project_gamma_event_payload(payload, fetched_at=_fetched_at())

    assert row.event_id == "evt-123"
    assert row.payload_hash == canonical_payload_hash(row.payload_json)
    # No createdAt/updatedAt -> falls back to fetched_at
    assert row.event_time_ns == int(_fetched_at().timestamp() * 1_000_000_000)
    assert row.slug is None
    assert row.market_count is None


def test_projects_full_payload_uses_updated_at() -> None:
    payload = {
        "id": 999,
        "slug": "btc-100k",
        "title": "Will BTC hit $100k by 2026?",
        "category": "Crypto",
        "active": True,
        "closed": False,
        "archived": False,
        "startDate": "2026-01-01T00:00:00Z",
        "endDate": "2026-12-31T23:59:59Z",
        "createdAt": "2025-12-01T10:00:00Z",
        "updatedAt": "2026-04-20T18:30:00Z",
        "volume": "1234567.89",
        "liquidity": 50000,
        "markets": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
    }

    row = project_gamma_event_payload(payload, fetched_at=_fetched_at())

    assert row.event_id == "999"
    assert row.slug == "btc-100k"
    assert row.title == "Will BTC hit $100k by 2026?"
    assert row.category == "Crypto"
    assert row.active is True
    assert row.closed is False
    assert row.archived is False
    assert row.start_date_iso == "2026-01-01T00:00:00Z"
    assert row.end_date_iso == "2026-12-31T23:59:59Z"
    assert row.volume_usd == pytest.approx(1234567.89)
    assert row.liquidity_usd == pytest.approx(50000.0)
    assert row.market_count == 3
    # Uses updatedAt, not createdAt or fetched_at
    expected_ns = int(datetime(2026, 4, 20, 18, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    assert row.event_time_ns == expected_ns


def test_payload_hash_is_stable_under_key_order() -> None:
    a = project_gamma_event_payload({"id": "x", "slug": "a", "title": "T"}, fetched_at=_fetched_at())
    b = project_gamma_event_payload({"title": "T", "id": "x", "slug": "a"}, fetched_at=_fetched_at())
    assert a.payload_hash == b.payload_hash


def test_missing_id_raises() -> None:
    with pytest.raises(ValueError, match="gamma_event_missing_id"):
        project_gamma_event_payload({"slug": "no-id"}, fetched_at=_fetched_at())


def test_malformed_timestamps_fall_back_to_fetched_at() -> None:
    payload = {"id": "evt", "updatedAt": "not-a-date", "createdAt": ""}
    row = project_gamma_event_payload(payload, fetched_at=_fetched_at())
    assert row.event_time_ns == int(_fetched_at().timestamp() * 1_000_000_000)


def test_end_to_end_writes_via_warehouse(tmp_path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)

    rows = [
        project_gamma_event_payload(
            {"id": "evt-1", "slug": "btc-100k", "active": True},
            fetched_at=_fetched_at(),
        ),
        project_gamma_event_payload(
            {"id": "evt-2", "slug": "eth-5k", "active": False},
            fetched_at=_fetched_at(),
        ),
    ]

    out_path = writer.write([r.to_warehouse_row() for r in rows])
    assert out_path.exists()

    import pyarrow.parquet as pq  # noqa: PLC0415  -- localized import

    table = pq.read_table(out_path)
    assert table.num_rows == 2
    assert set(table.column("event_id").to_pylist()) == {"evt-1", "evt-2"}
    assert all(s == GAMMA_SOURCE for s in table.column("source").to_pylist())
    # Round-trip: payload_json is parseable JSON
    for raw in table.column("payload_json").to_pylist():
        parsed = json.loads(raw)
        assert "id" in parsed
