"""Ingest Binance public klines (OHLCV) into the warehouse.

Binance's public ``/api/v3/klines`` endpoint returns up to 1000 candles per
request, ordered by ``open_time``. We paginate by advancing ``startTime`` to
the last ``close_time + 1`` of the previous page and stop when a page returns
empty or fully outside the requested window.

No authentication required — this hits the public REST surface.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from joint_research.warehouse.schema import CRYPTO_OHLCV

BINANCE_VENUE = "binance"
# Binance's public-data CDN — same kline schema, no auth, not geo-restricted in
# the US. The trading API (api.binance.com) returns 451 from US IPs; we never
# trade through here, only fetch historical data, so the CDN is the right path.
BINANCE_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
BINANCE_PAGE_LIMIT = 1000

SUPPORTED_INTERVALS = frozenset(
    {
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M",
    }
)


@dataclass(frozen=True)
class OhlcvRow:
    venue: str
    symbol: str
    interval: str
    open_time_ns: int
    close_time_ns: int
    open: float
    high: float
    low: float
    close: float
    volume_base: float
    volume_quote: float
    num_trades: int | None
    taker_buy_volume_base: float | None
    taker_buy_volume_quote: float | None
    payload_hash: str
    payload_json: str

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.open_time_ns,
            "source": f"{self.venue}.klines.{self.interval}",
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "venue": self.venue,
            "symbol": self.symbol,
            "interval": self.interval,
            "open_time_ns": self.open_time_ns,
            "close_time_ns": self.close_time_ns,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume_base": self.volume_base,
            "volume_quote": self.volume_quote,
            "num_trades": self.num_trades,
            "taker_buy_volume_base": self.taker_buy_volume_base,
            "taker_buy_volume_quote": self.taker_buy_volume_quote,
        }


def project_binance_kline(
    raw: list[Any],
    *,
    symbol: str,
    interval: str,
) -> OhlcvRow:
    """Project one Binance kline array into a typed warehouse row.

    Binance kline shape:
      [open_time_ms, open, high, low, close, volume,
       close_time_ms, quote_asset_volume, num_trades,
       taker_buy_base, taker_buy_quote, ignore]
    """

    if not isinstance(raw, list) or len(raw) < 11:
        raise ValueError(f"binance_kline_malformed:len={len(raw) if isinstance(raw, list) else 'na'}")

    open_time_ms = int(raw[0])
    close_time_ms = int(raw[6])
    payload_json = json.dumps(raw, separators=(",", ":"))
    payload_hash = hashlib.sha256(
        f"{BINANCE_VENUE}|{symbol}|{interval}|{open_time_ms}|{payload_json}".encode("utf-8")
    ).hexdigest()

    return OhlcvRow(
        venue=BINANCE_VENUE,
        symbol=symbol.upper(),
        interval=interval,
        open_time_ns=open_time_ms * 1_000_000,
        close_time_ns=close_time_ms * 1_000_000,
        open=float(raw[1]),
        high=float(raw[2]),
        low=float(raw[3]),
        close=float(raw[4]),
        volume_base=float(raw[5]),
        volume_quote=float(raw[7]),
        num_trades=_optional_int(raw[8]),
        taker_buy_volume_base=_optional_float(raw[9]),
        taker_buy_volume_quote=_optional_float(raw[10]),
        payload_hash=payload_hash,
        payload_json=payload_json,
    )


def project_binance_klines(
    raws: Iterable[list[Any]],
    *,
    symbol: str,
    interval: str,
) -> list[OhlcvRow]:
    return [project_binance_kline(r, symbol=symbol, interval=interval) for r in raws]


async def fetch_binance_klines_paged(
    *,
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int,
    client: httpx.AsyncClient | None = None,
    page_limit: int = BINANCE_PAGE_LIMIT,
    inter_request_sleep_s: float = 0.05,
) -> list[list[Any]]:
    """Page through ``/api/v3/klines`` until ``end_time_ms`` is covered.

    Returns the raw kline arrays concatenated. Caller is responsible for
    projecting them via ``project_binance_klines``.
    """

    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported_binance_interval:{interval}")
    if start_time_ms >= end_time_ms:
        raise ValueError(f"empty_window:start={start_time_ms}:end={end_time_ms}")

    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient(timeout=20.0)

    out: list[list[Any]] = []
    cursor = start_time_ms
    try:
        while cursor < end_time_ms:
            response = await http.get(
                BINANCE_KLINES_URL,
                params={
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_time_ms,
                    "limit": page_limit,
                },
            )
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list):
                raise TypeError(f"binance_klines_unexpected_payload:{type(page)!r}")
            if not page:
                break
            out.extend(page)

            last_close_ms = int(page[-1][6])
            next_cursor = last_close_ms + 1
            if next_cursor <= cursor:
                # Defensive: prevent infinite loops on a stuck cursor
                break
            cursor = next_cursor

            if len(page) < page_limit:
                break
            if inter_request_sleep_s > 0:
                await asyncio.sleep(inter_request_sleep_s)
    finally:
        if owns_client:
            await http.aclose()

    return out


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Re-export for symmetry with the table this ingestor populates.
TABLE = CRYPTO_OHLCV
