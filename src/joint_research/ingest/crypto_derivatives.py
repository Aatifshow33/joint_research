"""Public/no-auth crypto derivatives ingestion.

Uses Binance public futures/spot REST endpoints only:
- USD-M futures funding history for funding rates.
- USD-M futures mark price plus spot klines for perp/spot basis snapshots.

Projection is separated from fetching so tests do not need network access.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from joint_research.warehouse.schema import CRYPTO_DERIVATIVES

DERIVATIVES_VENUE = "binance"
BINANCE_FUNDING_RATE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
BINANCE_MARK_PRICE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
BINANCE_SPOT_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
DEFAULT_DERIVATIVES_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")


@dataclass(frozen=True)
class DerivativesRow:
    venue: str
    record_type: str
    symbol: str
    event_time_ns: int
    payload_hash: str
    payload_json: str
    funding_time_ns: int | None
    funding_rate: float | None
    mark_price: float | None
    spot_price: float | None
    basis_pct: float | None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": f"{self.venue}.derivatives.{self.record_type}",
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "venue": self.venue,
            "record_type": self.record_type,
            "symbol": self.symbol,
            "funding_time_ns": self.funding_time_ns,
            "funding_rate": self.funding_rate,
            "mark_price": self.mark_price,
            "spot_price": self.spot_price,
            "basis_pct": self.basis_pct,
        }


@dataclass(frozen=True)
class DerivativesFetchResult:
    rows: list[DerivativesRow]
    errors: tuple[str, ...]


def project_binance_funding_rate(payload: dict[str, Any]) -> DerivativesRow:
    symbol = _required_symbol(payload)
    funding_ms = _optional_int(payload.get("fundingTime"))
    if funding_ms is None:
        raise ValueError("funding_payload_missing_fundingTime")
    funding_rate = _optional_float(payload.get("fundingRate"))
    mark_price = _optional_float(payload.get("markPrice"))
    payload_json = _canonical_json(payload)
    return DerivativesRow(
        venue=DERIVATIVES_VENUE,
        record_type="funding_rate",
        symbol=symbol,
        event_time_ns=funding_ms * 1_000_000,
        payload_hash=_payload_hash("funding_rate", symbol, funding_ms, payload_json),
        payload_json=payload_json,
        funding_time_ns=funding_ms * 1_000_000,
        funding_rate=funding_rate,
        mark_price=mark_price,
        spot_price=None,
        basis_pct=None,
    )


def project_binance_funding_rates(payloads: Iterable[dict[str, Any]]) -> list[DerivativesRow]:
    rows: list[DerivativesRow] = []
    for payload in payloads:
        rows.append(project_binance_funding_rate(payload))
    return rows


def project_binance_mark_price_basis(
    mark_payload: dict[str, Any],
    *,
    spot_payload: list[Any] | None,
) -> DerivativesRow:
    symbol = _required_symbol(mark_payload)
    event_ms = (
        _optional_int(mark_payload.get("time"))
        or _optional_int(mark_payload.get("nextFundingTime"))
        or int(time.time() * 1000)
    )
    mark_price = _optional_float(mark_payload.get("markPrice"))
    spot_price = _spot_close(spot_payload)
    basis_pct = (
        (mark_price - spot_price) / spot_price
        if mark_price is not None and spot_price not in (None, 0.0)
        else None
    )
    raw_payload = {"mark": mark_payload, "spot": spot_payload}
    payload_json = _canonical_json(raw_payload)
    return DerivativesRow(
        venue=DERIVATIVES_VENUE,
        record_type="perp_basis",
        symbol=symbol,
        event_time_ns=event_ms * 1_000_000,
        payload_hash=_payload_hash("perp_basis", symbol, event_ms, payload_json),
        payload_json=payload_json,
        funding_time_ns=None,
        funding_rate=None,
        mark_price=mark_price,
        spot_price=spot_price,
        basis_pct=basis_pct,
    )


def classify_derivatives_regime(
    *,
    funding_rate: float | None,
    basis_pct: float | None,
    high_funding_threshold: float = 0.0001,
    premium_threshold: float = 0.0,
) -> tuple[str, str, str]:
    if funding_rate is None:
        funding_regime = "unknown_funding"
        funding_intensity = "unknown_funding"
    elif funding_rate > 0:
        funding_regime = "positive_funding"
        funding_intensity = (
            "high_funding" if funding_rate >= high_funding_threshold else "low_normal_funding"
        )
    elif funding_rate < 0:
        funding_regime = "negative_funding"
        funding_intensity = "low_normal_funding"
    else:
        funding_regime = "neutral_funding"
        funding_intensity = "low_normal_funding"

    if basis_pct is None:
        basis_regime = "unknown_basis"
    elif basis_pct > premium_threshold:
        basis_regime = "perp_premium"
    elif basis_pct < -premium_threshold:
        basis_regime = "perp_discount"
    else:
        basis_regime = "flat_basis"

    return funding_regime, funding_intensity, basis_regime


async def fetch_derivatives_rows(
    *,
    symbols: Iterable[str] = DEFAULT_DERIVATIVES_SYMBOLS,
    limit: int = 24,
    client: httpx.AsyncClient | None = None,
) -> DerivativesFetchResult:
    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient(timeout=20.0)
    rows: list[DerivativesRow] = []
    errors: list[str] = []
    try:
        for symbol_raw in symbols:
            symbol = symbol_raw.upper().strip()
            if not symbol:
                continue
            try:
                funding_payloads = await fetch_binance_funding_rates(
                    symbol=symbol,
                    limit=limit,
                    client=http,
                )
                rows.extend(project_binance_funding_rates(funding_payloads))
            except Exception as exc:  # noqa: BLE001 - source-specific graceful degradation
                errors.append(f"{symbol}:funding:{type(exc).__name__}:{exc}")
            try:
                mark_payload = await fetch_binance_mark_price(symbol=symbol, client=http)
                spot_payload = await fetch_latest_spot_kline(symbol=symbol, client=http)
                rows.append(
                    project_binance_mark_price_basis(
                        mark_payload,
                        spot_payload=spot_payload,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - source-specific graceful degradation
                errors.append(f"{symbol}:basis:{type(exc).__name__}:{exc}")
    finally:
        if owns_client:
            await http.aclose()
    return DerivativesFetchResult(rows=rows, errors=tuple(errors))


async def fetch_binance_funding_rates(
    *,
    symbol: str,
    limit: int,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get(
        BINANCE_FUNDING_RATE_URL,
        params={"symbol": symbol.upper(), "limit": limit},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise TypeError(f"funding_unexpected_payload:{type(payload)!r}")
    return [row for row in payload if isinstance(row, dict)]


async def fetch_binance_mark_price(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    response = await client.get(BINANCE_MARK_PRICE_URL, params={"symbol": symbol.upper()})
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"mark_price_unexpected_payload:{type(payload)!r}")
    return payload


async def fetch_latest_spot_kline(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> list[Any] | None:
    response = await client.get(
        BINANCE_SPOT_KLINES_URL,
        params={"symbol": symbol.upper(), "interval": "1h", "limit": 1},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    return first if isinstance(first, list) else None


def _required_symbol(payload: dict[str, Any]) -> str:
    symbol = payload.get("symbol")
    if symbol is None:
        raise ValueError("derivatives_payload_missing_symbol")
    return str(symbol).upper()


def _spot_close(payload: list[Any] | None) -> float | None:
    if payload is None or len(payload) < 5:
        return None
    return _optional_float(payload[4])


def _payload_hash(record_type: str, symbol: str, event_ms: int, payload_json: str) -> str:
    return hashlib.sha256(
        f"{DERIVATIVES_VENUE}|{record_type}|{symbol}|{event_ms}|{payload_json}".encode("utf-8")
    ).hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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


TABLE = CRYPTO_DERIVATIVES
