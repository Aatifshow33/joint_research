from __future__ import annotations

import json
from pathlib import Path

import duckdb

from joint_research.ingest.binance_klines import (
    project_binance_klines,
)
from joint_research.ingest.polymarket_gamma import project_gamma_event_payloads
from joint_research.warehouse import (
    CRYPTO_OHLCV,
    POLYMARKET_GAMMA_EVENTS,
    ParquetWriter,
    WarehousePaths,
    register_views,
)


def _kline(open_ms: int, close_ms: int, close: float) -> list:
    return [
        open_ms,
        f"{close:.2f}",
        f"{close + 50:.2f}",
        f"{close - 50:.2f}",
        f"{close:.2f}",
        "1.0",
        close_ms,
        f"{close:.2f}",
        10,
        "0.5",
        f"{close / 2:.2f}",
        "0",
    ]


def _seed_warehouse(tmp_path: Path) -> WarehousePaths:
    paths = WarehousePaths(root=tmp_path)

    # Two BTC bars, one hour apart.
    ohlcv_writer = ParquetWriter(table=CRYPTO_OHLCV, paths=paths)
    rows = project_binance_klines(
        [
            _kline(1_700_000_000_000, 1_700_003_599_999, close=30000.0),
            _kline(1_700_003_600_000, 1_700_007_199_999, close=30300.0),
        ],
        symbol="BTCUSDT",
        interval="1h",
    )
    ohlcv_writer.write([r.to_warehouse_row() for r in rows])

    # Two events: one crypto-relevant, one off-topic.
    from datetime import datetime, timezone  # local to avoid module-level coupling

    fetched = datetime(2026, 4, 27, tzinfo=timezone.utc)
    events_writer = ParquetWriter(table=POLYMARKET_GAMMA_EVENTS, paths=paths)
    rows_e = project_gamma_event_payloads(
        [
            {"id": "btc-100k", "slug": "bitcoin-100k", "title": "Will BTC hit $100k?"},
            {"id": "macron", "slug": "macron-out", "title": "Macron out by 2026?"},
        ],
        fetched_at=fetched,
    )
    events_writer.write([r.to_warehouse_row() for r in rows_e])
    return paths


def test_views_register_and_filter_correctly(tmp_path: Path) -> None:
    paths = _seed_warehouse(tmp_path)

    con = duckdb.connect()
    register_views(con, paths)

    # Base views populated
    assert con.execute("SELECT count(*) FROM crypto_ohlcv").fetchone() == (2,)
    assert con.execute("SELECT count(*) FROM polymarket_gamma_events").fetchone() == (2,)

    # crypto_returns: first row's log_return is null (no prior bar)
    rows = con.execute(
        "SELECT log_return FROM crypto_returns ORDER BY open_time_ns"
    ).fetchall()
    assert rows[0][0] is None
    assert rows[1][0] is not None
    assert rows[1][0] > 0  # 30000 -> 30300 is positive

    # polymarket_crypto_events: filters to BTC/crypto matches only
    crypto_events = con.execute(
        "SELECT event_id FROM polymarket_crypto_events"
    ).fetchall()
    assert crypto_events == [("btc-100k",)]


def test_views_dedupe_on_repeat_ingest(tmp_path: Path) -> None:
    paths = _seed_warehouse(tmp_path)

    # Re-write the same OHLCV row again — should produce a second shard.
    ohlcv_writer = ParquetWriter(table=CRYPTO_OHLCV, paths=paths)
    rows = project_binance_klines(
        [_kline(1_700_000_000_000, 1_700_003_599_999, close=30000.0)],
        symbol="BTCUSDT",
        interval="1h",
    )
    ohlcv_writer.write([r.to_warehouse_row() for r in rows])

    shards = list((paths.root / CRYPTO_OHLCV.name).rglob("*.parquet"))
    assert len(shards) >= 2

    con = duckdb.connect()
    register_views(con, paths)

    # Despite multiple shards, the view dedups: still 2 distinct (symbol, open_time_ns)
    n = con.execute("SELECT count(*) FROM crypto_ohlcv").fetchone()
    assert n == (2,)


def test_payload_json_roundtrip_through_view(tmp_path: Path) -> None:
    paths = _seed_warehouse(tmp_path)
    con = duckdb.connect()
    register_views(con, paths)

    payloads = con.execute(
        "SELECT payload_json FROM polymarket_crypto_events"
    ).fetchall()
    assert len(payloads) == 1
    parsed = json.loads(payloads[0][0])
    assert parsed["id"] == "btc-100k"
