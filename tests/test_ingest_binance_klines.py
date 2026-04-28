from __future__ import annotations

import json

import httpx
import pytest

from joint_research.ingest.binance_klines import (
    BINANCE_VENUE,
    fetch_binance_klines_paged,
    project_binance_kline,
    project_binance_klines,
)
from joint_research.warehouse import CRYPTO_OHLCV, ParquetWriter, WarehousePaths


def _kline(open_ms: int, close_ms: int, close: float = 30000.0) -> list:
    return [
        open_ms,
        "29900.00",
        "30100.00",
        "29800.00",
        f"{close:.2f}",
        "12.345",
        close_ms,
        "370350.0",
        100,
        "5.0",
        "150000.0",
        "0",
    ]


def test_projects_kline_to_typed_row() -> None:
    raw = _kline(open_ms=1_700_000_000_000, close_ms=1_700_000_059_999, close=30100.5)

    row = project_binance_kline(raw, symbol="btcusdt", interval="1m")

    assert row.venue == BINANCE_VENUE
    assert row.symbol == "BTCUSDT"
    assert row.interval == "1m"
    assert row.open_time_ns == 1_700_000_000_000 * 1_000_000
    assert row.close_time_ns == 1_700_000_059_999 * 1_000_000
    assert row.open == pytest.approx(29900.0)
    assert row.high == pytest.approx(30100.0)
    assert row.low == pytest.approx(29800.0)
    assert row.close == pytest.approx(30100.5)
    assert row.volume_base == pytest.approx(12.345)
    assert row.volume_quote == pytest.approx(370350.0)
    assert row.num_trades == 100
    assert row.taker_buy_volume_base == pytest.approx(5.0)
    assert row.taker_buy_volume_quote == pytest.approx(150000.0)
    assert json.loads(row.payload_json)[0] == 1_700_000_000_000


def test_malformed_kline_raises() -> None:
    with pytest.raises(ValueError, match="binance_kline_malformed"):
        project_binance_kline([1, 2, 3], symbol="BTCUSDT", interval="1h")


def test_payload_hash_distinguishes_open_times() -> None:
    a = project_binance_kline(
        _kline(open_ms=1_700_000_000_000, close_ms=1_700_000_059_999),
        symbol="BTCUSDT",
        interval="1m",
    )
    b = project_binance_kline(
        _kline(open_ms=1_700_000_060_000, close_ms=1_700_000_119_999),
        symbol="BTCUSDT",
        interval="1m",
    )
    assert a.payload_hash != b.payload_hash


def test_writes_via_warehouse(tmp_path) -> None:
    paths = WarehousePaths(root=tmp_path)
    writer = ParquetWriter(table=CRYPTO_OHLCV, paths=paths)

    rows = project_binance_klines(
        [
            _kline(open_ms=1_700_000_000_000, close_ms=1_700_000_059_999),
            _kline(open_ms=1_700_000_060_000, close_ms=1_700_000_119_999),
        ],
        symbol="BTCUSDT",
        interval="1m",
    )

    out = writer.write([r.to_warehouse_row() for r in rows])
    assert out.exists()


@pytest.mark.asyncio
async def test_paginator_advances_cursor_until_window_closed() -> None:
    """Mock transport: simulate two pages followed by an empty page."""

    pages = [
        # First page: full size, simulating limit reached
        [_kline(open_ms=1_000_000, close_ms=1_059_999) for _ in range(3)],
        # Second page: partial — paginator should stop after this
        [_kline(open_ms=1_060_000, close_ms=1_119_999)],
    ]

    call_count = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        idx = call_count["n"] - 1
        if idx < len(pages):
            return httpx.Response(200, json=pages[idx])
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_binance_klines_paged(
            symbol="BTCUSDT",
            interval="1m",
            start_time_ms=1_000_000,
            end_time_ms=2_000_000,
            client=client,
            page_limit=3,
            inter_request_sleep_s=0.0,
        )

    assert len(out) == 4
    # First page was full (3 == limit) so paginator continues; second page is
    # partial (1 < limit=3) so it stops without a third request.
    assert call_count["n"] == 2
