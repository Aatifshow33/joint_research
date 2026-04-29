"""Public/no-auth crypto derivatives ingestion.

Primary source:
- Binance futures/spot REST APIs.

Fallback source:
- Binance public data ZIP files hosted on data.binance.vision.

Projection is separated from source-specific fetching so tests do not need
network access.
"""

from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from csv import DictReader, reader
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable

import httpx

from joint_research.warehouse.schema import CRYPTO_DERIVATIVES

DERIVATIVES_VENUE = "binance"
BINANCE_API_SOURCE = "binance_api"
BINANCE_PUBLIC_DATA_SOURCE = "binance_public_data"
BINANCE_FUNDING_RATE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
BINANCE_MARK_PRICE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
BINANCE_SPOT_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
BINANCE_PUBLIC_DATA_BASE_URL = "https://data.binance.vision/data"
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
    source: str | None = None

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": self.source or f"{self.venue}.derivatives.{self.record_type}",
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
    source_attempts: tuple["DerivativesSourceAttempt", ...] = ()


@dataclass(frozen=True)
class DerivativesSourceAttempt:
    source: str
    symbol: str
    record_type: str
    status: str
    rows: int
    detail: str | None = None


def project_binance_funding_rate(
    payload: dict[str, Any],
    *,
    venue: str = DERIVATIVES_VENUE,
    source: str = BINANCE_API_SOURCE,
) -> DerivativesRow:
    symbol = _required_symbol(payload)
    funding_ms = _optional_int(payload.get("fundingTime"))
    if funding_ms is None:
        raise ValueError("funding_payload_missing_fundingTime")
    funding_rate = _optional_float(payload.get("fundingRate"))
    mark_price = _optional_float(payload.get("markPrice"))
    payload_json = _canonical_json(payload)
    return DerivativesRow(
        venue=venue,
        record_type="funding_rate",
        symbol=symbol,
        event_time_ns=funding_ms * 1_000_000,
        payload_hash=_payload_hash("funding_rate", symbol, funding_ms, payload_json, venue=venue),
        payload_json=payload_json,
        funding_time_ns=funding_ms * 1_000_000,
        funding_rate=funding_rate,
        mark_price=mark_price,
        spot_price=None,
        basis_pct=None,
        source=f"{venue}.derivatives.{source}.funding_rate",
    )


def project_binance_funding_rates(
    payloads: Iterable[dict[str, Any]],
    *,
    venue: str = DERIVATIVES_VENUE,
    source: str = BINANCE_API_SOURCE,
) -> list[DerivativesRow]:
    rows: list[DerivativesRow] = []
    for payload in payloads:
        rows.append(project_binance_funding_rate(payload, venue=venue, source=source))
    return rows


def project_binance_mark_price_basis(
    mark_payload: dict[str, Any],
    *,
    spot_payload: list[Any] | None,
    venue: str = DERIVATIVES_VENUE,
    source: str = BINANCE_API_SOURCE,
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
        venue=venue,
        record_type="perp_basis",
        symbol=symbol,
        event_time_ns=event_ms * 1_000_000,
        payload_hash=_payload_hash("perp_basis", symbol, event_ms, payload_json, venue=venue),
        payload_json=payload_json,
        funding_time_ns=None,
        funding_rate=None,
        mark_price=mark_price,
        spot_price=spot_price,
        basis_pct=basis_pct,
        source=f"{venue}.derivatives.{source}.perp_basis",
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
    attempts: list[DerivativesSourceAttempt] = []
    try:
        for symbol_raw in symbols:
            symbol = symbol_raw.upper().strip()
            if not symbol:
                continue
            funding_rows, funding_attempts, funding_errors = await _fetch_funding_with_fallback(
                symbol=symbol,
                limit=limit,
                client=http,
            )
            rows.extend(funding_rows)
            attempts.extend(funding_attempts)
            errors.extend(funding_errors)

            basis_rows, basis_attempts, basis_errors = await _fetch_basis_with_fallback(
                symbol=symbol,
                client=http,
            )
            rows.extend(basis_rows)
            attempts.extend(basis_attempts)
            errors.extend(basis_errors)
    finally:
        if owns_client:
            await http.aclose()
    return DerivativesFetchResult(rows=rows, errors=tuple(errors), source_attempts=tuple(attempts))


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


async def fetch_binance_public_funding_rates(
    *,
    symbol: str,
    limit: int,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for month_start in _recent_month_starts(limit_months=6):
        url = (
            f"{BINANCE_PUBLIC_DATA_BASE_URL}/futures/um/monthly/fundingRate/{symbol.upper()}/"
            f"{symbol.upper()}-fundingRate-{month_start:%Y-%m}.zip"
        )
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                continue
            raise
        parsed = _parse_public_funding_zip(response.content, symbol=symbol)
        if parsed:
            rows.extend(parsed)
        if len(rows) >= limit:
            break
    if not rows:
        raise RuntimeError("public_funding_rate_rows_not_found")
    rows.sort(key=lambda payload: _optional_int(payload.get("fundingTime")) or 0)
    return rows[-limit:]


async def fetch_binance_public_mark_price(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    payload = await _fetch_public_latest_kline_payload(
        symbol=symbol,
        client=client,
        daily_path_prefix="futures/um/daily/markPriceKlines",
        monthly_path_prefix="futures/um/monthly/markPriceKlines",
    )
    close_time_ms = _parse_binance_time_like_ms(payload[6]) or _parse_binance_time_like_ms(payload[0])
    if close_time_ms is None:
        close_time_ms = int(time.time() * 1000)
    return {
        "symbol": symbol.upper(),
        "time": close_time_ms,
        "markPrice": payload[4],
    }


async def fetch_binance_public_spot_kline(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> list[Any] | None:
    payload = await _fetch_public_latest_kline_payload(
        symbol=symbol,
        client=client,
        daily_path_prefix="spot/daily/klines",
        monthly_path_prefix="spot/monthly/klines",
    )
    return payload


async def _fetch_funding_with_fallback(
    *,
    symbol: str,
    limit: int,
    client: httpx.AsyncClient,
) -> tuple[list[DerivativesRow], list[DerivativesSourceAttempt], list[str]]:
    attempts: list[DerivativesSourceAttempt] = []
    errors: list[str] = []
    for source_name, fetcher in (
        (
            BINANCE_API_SOURCE,
            lambda: fetch_binance_funding_rates(symbol=symbol, limit=limit, client=client),
        ),
        (
            BINANCE_PUBLIC_DATA_SOURCE,
            lambda: fetch_binance_public_funding_rates(symbol=symbol, limit=limit, client=client),
        ),
    ):
        try:
            payloads = await fetcher()
            rows = project_binance_funding_rates(
                payloads,
                venue=DERIVATIVES_VENUE,
                source=source_name,
            )
            if not rows:
                detail = "empty_rows"
                attempts.append(
                    DerivativesSourceAttempt(
                        source=source_name,
                        symbol=symbol,
                        record_type="funding_rate",
                        status="failed",
                        rows=0,
                        detail=detail,
                    )
                )
                errors.append(f"{symbol}:funding_rate:{source_name}:{detail}")
                continue
            attempts.append(
                DerivativesSourceAttempt(
                    source=source_name,
                    symbol=symbol,
                    record_type="funding_rate",
                    status="success",
                    rows=len(rows),
                )
            )
            return rows, attempts, errors
        except Exception as exc:  # noqa: BLE001 - source-specific graceful degradation
            detail = _format_source_error(exc)
            attempts.append(
                DerivativesSourceAttempt(
                    source=source_name,
                    symbol=symbol,
                    record_type="funding_rate",
                    status="failed",
                    rows=0,
                    detail=detail,
                )
            )
            errors.append(f"{symbol}:funding_rate:{source_name}:{detail}")
    return [], attempts, errors


async def _fetch_basis_with_fallback(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> tuple[list[DerivativesRow], list[DerivativesSourceAttempt], list[str]]:
    attempts: list[DerivativesSourceAttempt] = []
    errors: list[str] = []
    for source_name, fetcher in (
        (
            BINANCE_API_SOURCE,
            lambda: _fetch_binance_api_basis_inputs(symbol=symbol, client=client),
        ),
        (
            BINANCE_PUBLIC_DATA_SOURCE,
            lambda: _fetch_binance_public_basis_inputs(symbol=symbol, client=client),
        ),
    ):
        try:
            mark_payload, spot_payload = await fetcher()
            row = project_binance_mark_price_basis(
                mark_payload,
                spot_payload=spot_payload,
                venue=DERIVATIVES_VENUE,
                source=source_name,
            )
            attempts.append(
                DerivativesSourceAttempt(
                    source=source_name,
                    symbol=symbol,
                    record_type="perp_basis",
                    status="success",
                    rows=1,
                )
            )
            return [row], attempts, errors
        except Exception as exc:  # noqa: BLE001 - source-specific graceful degradation
            detail = _format_source_error(exc)
            attempts.append(
                DerivativesSourceAttempt(
                    source=source_name,
                    symbol=symbol,
                    record_type="perp_basis",
                    status="failed",
                    rows=0,
                    detail=detail,
                )
            )
            errors.append(f"{symbol}:perp_basis:{source_name}:{detail}")
    return [], attempts, errors


async def _fetch_binance_api_basis_inputs(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], list[Any] | None]:
    mark_payload = await fetch_binance_mark_price(symbol=symbol, client=client)
    spot_payload = await fetch_latest_spot_kline(symbol=symbol, client=client)
    return mark_payload, spot_payload


async def _fetch_binance_public_basis_inputs(
    *,
    symbol: str,
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], list[Any] | None]:
    mark_payload = await fetch_binance_public_mark_price(symbol=symbol, client=client)
    spot_payload = await fetch_binance_public_spot_kline(symbol=symbol, client=client)
    return mark_payload, spot_payload


async def _fetch_public_latest_kline_payload(
    *,
    symbol: str,
    client: httpx.AsyncClient,
    daily_path_prefix: str,
    monthly_path_prefix: str,
) -> list[Any]:
    # Prefer recent daily files, then fall back to recent monthly archives.
    for dt in _recent_dates(limit_days=7):
        url = (
            f"{BINANCE_PUBLIC_DATA_BASE_URL}/{daily_path_prefix}/{symbol.upper()}/1h/"
            f"{symbol.upper()}-1h-{dt:%Y-%m-%d}.zip"
        )
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                continue
            raise
        parsed = _parse_public_kline_zip(response.content)
        if parsed:
            return parsed[-1]

    for month_start in _recent_month_starts(limit_months=6):
        url = (
            f"{BINANCE_PUBLIC_DATA_BASE_URL}/{monthly_path_prefix}/{symbol.upper()}/1h/"
            f"{symbol.upper()}-1h-{month_start:%Y-%m}.zip"
        )
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                continue
            raise
        parsed = _parse_public_kline_zip(response.content)
        if parsed:
            return parsed[-1]

    raise RuntimeError("public_kline_rows_not_found")


def _parse_public_funding_zip(content: bytes, *, symbol: str) -> list[dict[str, Any]]:
    csv_text = _read_first_zip_member_text(content)
    rows: list[dict[str, Any]] = []
    for record in DictReader(io.StringIO(csv_text)):
        funding_time = _optional_int(record.get("fundingTime") or record.get("calc_time"))
        if funding_time is None:
            continue
        rows.append(
            {
                "symbol": symbol.upper(),
                "fundingTime": funding_time,
                "fundingRate": record.get("fundingRate") or record.get("last_funding_rate"),
                "markPrice": record.get("markPrice"),
            }
        )
    return rows


def _parse_public_kline_zip(content: bytes) -> list[list[Any]]:
    csv_text = _read_first_zip_member_text(content)
    parsed_rows: list[list[Any]] = []
    for idx, row in enumerate(reader(io.StringIO(csv_text))):
        if not row:
            continue
        if idx == 0 and _optional_int(row[0]) is None:
            continue
        parsed_rows.append(row)
    return parsed_rows


def _read_first_zip_member_text(content: bytes) -> str:
    archive = zipfile.ZipFile(io.BytesIO(content))
    names = archive.namelist()
    if not names:
        raise ValueError("zip_archive_empty")
    return archive.read(names[0]).decode("utf-8")


def _recent_dates(*, limit_days: int) -> list[date]:
    today = datetime.now(UTC).date()
    return [today - timedelta(days=offset) for offset in range(1, limit_days + 1)]


def _recent_month_starts(*, limit_months: int) -> list[date]:
    anchor = datetime.now(UTC).date().replace(day=1)
    out: list[date] = []
    month_cursor = anchor
    for _ in range(limit_months):
        month_cursor = _previous_month(month_cursor)
        out.append(month_cursor)
    return out


def _previous_month(month_start: date) -> date:
    previous_day = month_start - timedelta(days=1)
    return previous_day.replace(day=1)


def _parse_binance_time_like_ms(value: Any) -> int | None:
    raw = _optional_int(value)
    if raw is None:
        return None
    # Binance public spot files can encode timestamps in microseconds.
    return raw // 1000 if raw > 10_000_000_000_000 else raw


def _format_source_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_{exc.response.status_code}:{exc}"
    if isinstance(exc, httpx.TimeoutException):
        return f"timeout:{exc}"
    return f"{type(exc).__name__}:{exc}"


def _required_symbol(payload: dict[str, Any]) -> str:
    symbol = payload.get("symbol")
    if symbol is None:
        raise ValueError("derivatives_payload_missing_symbol")
    return str(symbol).upper()


def _spot_close(payload: list[Any] | None) -> float | None:
    if payload is None or len(payload) < 5:
        return None
    return _optional_float(payload[4])


def _payload_hash(
    record_type: str,
    symbol: str,
    event_ms: int,
    payload_json: str,
    *,
    venue: str,
) -> str:
    return hashlib.sha256(
        f"{venue}|{record_type}|{symbol}|{event_ms}|{payload_json}".encode("utf-8")
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
