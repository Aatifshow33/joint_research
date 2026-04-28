"""Ingest US-equity OHLCV from Yahoo Finance via the ``yfinance`` package.

Daily bars only at first — intraday is rate-limited and rarely needed for
the swing-style strategies the agent crew runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from joint_research.warehouse.schema import STOCK_OHLCV

YFINANCE_VENUE = "yfinance"
YFINANCE_SOURCE = "yfinance.daily"


@dataclass(frozen=True)
class StockOhlcvRow:
    venue: str
    symbol: str
    interval: str
    open_time_ns: int
    close_time_ns: int
    open: float
    high: float
    low: float
    close: float
    adj_close: float | None
    volume: float
    dividend: float | None
    split_ratio: float | None
    payload_hash: str
    payload_json: str

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.open_time_ns,
            "source": YFINANCE_SOURCE,
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
            "adj_close": self.adj_close,
            "volume": self.volume,
            "dividend": self.dividend,
            "split_ratio": self.split_ratio,
        }


def project_yfinance_bar(
    *,
    symbol: str,
    timestamp_utc: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    adj_close: float | None,
    volume: float,
    dividend: float | None = None,
    split_ratio: float | None = None,
    interval: str = "1d",
) -> StockOhlcvRow:
    """Project one yfinance OHLCV row into a typed warehouse row.

    yfinance returns daily bars timestamped at midnight (exchange-local).
    We treat the open_time as the bar start (UTC midnight of trade date) and
    close_time as 23:59:59.999999999 UTC of the same date — this keeps daily
    bars on the same UTC-day boundaries as our crypto and macro data.
    """

    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware UTC")

    open_time_ns = int(timestamp_utc.timestamp() * 1_000_000_000)
    close_time_ns = open_time_ns + 86_400_000_000_000 - 1  # one full day minus 1ns

    h_safe = max(high, open_, close)
    l_safe = min(low, open_, close)

    payload_dict = {
        "symbol": symbol,
        "ts": int(timestamp_utc.timestamp()),
        "o": float(open_),
        "h": float(h_safe),
        "l": float(l_safe),
        "c": float(close),
        "ac": float(adj_close) if adj_close is not None else None,
        "v": float(volume),
        "d": float(dividend) if dividend is not None else None,
        "s": float(split_ratio) if split_ratio is not None else None,
    }
    payload_json = _canonical_json(payload_dict)
    payload_hash = hashlib.sha256(
        f"{YFINANCE_VENUE}|{symbol}|{interval}|{open_time_ns}|{payload_json}".encode("utf-8")
    ).hexdigest()

    return StockOhlcvRow(
        venue=YFINANCE_VENUE,
        symbol=symbol.upper(),
        interval=interval,
        open_time_ns=open_time_ns,
        close_time_ns=close_time_ns,
        open=float(open_),
        high=float(h_safe),
        low=float(l_safe),
        close=float(close),
        adj_close=float(adj_close) if adj_close is not None else None,
        volume=float(volume),
        dividend=float(dividend) if dividend is not None else None,
        split_ratio=float(split_ratio) if split_ratio is not None else None,
        payload_hash=payload_hash,
        payload_json=payload_json,
    )


def project_yfinance_dataframe(
    df: Any,
    *,
    symbol: str,
    interval: str = "1d",
) -> list[StockOhlcvRow]:
    """Project a yfinance DataFrame to typed rows.

    yfinance's ``Ticker.history()`` returns a DataFrame indexed by tz-aware
    DatetimeIndex with columns: Open, High, Low, Close, Volume, Dividends,
    Stock Splits. We don't import pandas at module import time so the
    ingest module stays cheap to import in tests.
    """

    rows: list[StockOhlcvRow] = []
    if df is None or len(df) == 0:
        return rows
    for ts, record in df.iterrows():
        # ``ts`` is a tz-aware Timestamp (Yahoo returns America/New_York for US)
        ts_utc = ts.to_pydatetime().astimezone(timezone.utc)
        # Normalize to midnight UTC of the trade date — yfinance daily bars
        # represent the whole trading day; the timestamp is the session date.
        ts_utc = datetime(ts_utc.year, ts_utc.month, ts_utc.day, tzinfo=timezone.utc)
        open_ = float(record.get("Open"))
        high = float(record.get("High"))
        low = float(record.get("Low"))
        close = float(record.get("Close"))
        volume = float(record.get("Volume"))
        # ``Adj Close`` only present in some pulls; fall back to Close.
        ac_raw = record.get("Adj Close")
        adj_close = float(ac_raw) if ac_raw is not None else None
        div_raw = record.get("Dividends")
        dividend = float(div_raw) if div_raw is not None else None
        split_raw = record.get("Stock Splits")
        split_ratio = float(split_raw) if split_raw is not None else None
        rows.append(
            project_yfinance_bar(
                symbol=symbol,
                timestamp_utc=ts_utc,
                open_=open_,
                high=high,
                low=low,
                close=close,
                adj_close=adj_close,
                volume=volume,
                dividend=dividend,
                split_ratio=split_ratio,
                interval=interval,
            )
        )
    return rows


def _canonical_json(d: dict) -> str:
    import json  # noqa: PLC0415  -- localized import

    return json.dumps(d, sort_keys=True, separators=(",", ":"))


TABLE = STOCK_OHLCV
