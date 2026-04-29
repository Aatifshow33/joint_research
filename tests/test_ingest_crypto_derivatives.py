from __future__ import annotations

import json
import zipfile
from io import BytesIO

import duckdb
import httpx
import pytest
from joint_research.ingest.crypto_derivatives import (
    BINANCE_FUNDING_RATE_URL,
    BINANCE_MARK_PRICE_URL,
    BINANCE_PUBLIC_DATA_BASE_URL,
    DERIVATIVES_VENUE,
    DerivativesSourceAttempt,
    classify_derivatives_regime,
    fetch_derivatives_rows,
    project_binance_funding_rate,
    project_binance_mark_price_basis,
)
from joint_research.warehouse import (
    CRYPTO_DERIVATIVES,
    ParquetWriter,
    WarehousePaths,
    register_views,
)


def test_projects_funding_rate_payload() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "fundingTime": 1_700_000_000_000,
        "fundingRate": "0.00010000",
        "markPrice": "30000.0",
    }

    row = project_binance_funding_rate(payload)

    assert row.venue == DERIVATIVES_VENUE
    assert row.record_type == "funding_rate"
    assert row.symbol == "BTCUSDT"
    assert row.event_time_ns == 1_700_000_000_000 * 1_000_000
    assert row.funding_rate == pytest.approx(0.0001)
    assert row.mark_price == pytest.approx(30000.0)
    assert row.spot_price is None
    assert row.basis_pct is None
    assert json.loads(row.payload_json)["fundingRate"] == "0.00010000"


def test_perp_basis_calculation() -> None:
    mark_payload = {
        "symbol": "ETHUSDT",
        "time": 1_700_000_000_000,
        "markPrice": "2020.0",
    }
    spot_payload = [
        1_700_000_000_000,
        "1990.0",
        "2030.0",
        "1985.0",
        "2000.0",
        "1.0",
        1_700_003_599_999,
        "2000.0",
        1,
        "0.5",
        "1000.0",
        "0",
    ]

    row = project_binance_mark_price_basis(mark_payload, spot_payload=spot_payload)

    assert row.record_type == "perp_basis"
    assert row.symbol == "ETHUSDT"
    assert row.mark_price == pytest.approx(2020.0)
    assert row.spot_price == pytest.approx(2000.0)
    assert row.basis_pct == pytest.approx(0.01)


def test_missing_spot_data_returns_basis_row_without_basis() -> None:
    row = project_binance_mark_price_basis(
        {"symbol": "SOLUSDT", "time": 1_700_000_000_000, "markPrice": "100.0"},
        spot_payload=None,
    )

    assert row.record_type == "perp_basis"
    assert row.spot_price is None
    assert row.basis_pct is None


def test_derivatives_payload_hash_is_deterministic() -> None:
    payload = {
        "symbol": "XRPUSDT",
        "fundingTime": 1_700_000_000_000,
        "fundingRate": "-0.00005000",
    }

    a = project_binance_funding_rate(payload)
    b = project_binance_funding_rate(dict(reversed(list(payload.items()))))

    assert a.payload_hash == b.payload_hash
    assert a.to_warehouse_row()["payload_hash"] == a.payload_hash


def test_regime_classification() -> None:
    assert classify_derivatives_regime(funding_rate=0.0002, basis_pct=0.002) == (
        "positive_funding",
        "high_funding",
        "perp_premium",
    )
    assert classify_derivatives_regime(funding_rate=-0.00001, basis_pct=-0.002) == (
        "negative_funding",
        "low_normal_funding",
        "perp_discount",
    )


def test_derivatives_views_register_regime(tmp_path) -> None:
    paths = WarehousePaths(root=tmp_path)
    funding = project_binance_funding_rate(
        {
            "symbol": "BTCUSDT",
            "fundingTime": 1_700_000_000_000,
            "fundingRate": "0.0002",
            "markPrice": "30000.0",
        }
    )
    basis = project_binance_mark_price_basis(
        {"symbol": "BTCUSDT", "time": 1_700_000_000_000, "markPrice": "30300.0"},
        spot_payload=[
            1_700_000_000_000,
            "30000.0",
            "30300.0",
            "29900.0",
            "30000.0",
            "1.0",
            1_700_003_599_999,
            "30000.0",
            1,
            "0.5",
            "15000.0",
            "0",
        ],
    )
    ParquetWriter(table=CRYPTO_DERIVATIVES, paths=paths).write(
        [funding.to_warehouse_row(), basis.to_warehouse_row()]
    )

    con = duckdb.connect()
    register_views(con, paths)

    funding_rows = con.execute("SELECT symbol, funding_rate FROM crypto_funding_rates").fetchall()
    basis_rows = con.execute("SELECT symbol, basis_pct FROM crypto_perp_basis").fetchall()
    regime = con.execute(
        """
        SELECT funding_regime, funding_intensity, basis_regime
        FROM crypto_derivatives_regime
        """
    ).fetchall()

    assert funding_rows == [("BTCUSDT", pytest.approx(0.0002))]
    assert basis_rows == [("BTCUSDT", pytest.approx(0.01))]
    assert regime == [("positive_funding", "high_funding", "perp_premium")]


def _zip_csv(filename: str, content: str) -> bytes:
    bio = BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_fallback_activates_after_451_and_preserves_source_metadata() -> None:
    funding_csv = "\n".join(
        [
            "calc_time,funding_interval_hours,last_funding_rate",
            "1700000000000,8,0.00010",
            "1700003600000,8,0.00020",
        ]
    )
    mark_csv = "\n".join(
        [
            "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore",
            "1700000000000,30000,30100,29900,30050,0,1700003599999,0,0,0,0,0",
        ]
    )
    spot_csv = "\n".join(
        [
            "1700000000000000,29900,30100,29800,30000,1,1700003599999999,1000,1,0.5,500,0",
        ]
    )
    funding_zip = _zip_csv("BTCUSDT-fundingRate-2026-03.csv", funding_csv)
    mark_zip = _zip_csv("BTCUSDT-1h-2026-04-27.csv", mark_csv)
    spot_zip = _zip_csv("BTCUSDT-1h-2026-04-27.csv", spot_csv)

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        full_url = str(request.url)
        if full_url.startswith(BINANCE_FUNDING_RATE_URL):
            return httpx.Response(451, text="geo blocked")
        if full_url.startswith(BINANCE_MARK_PRICE_URL):
            return httpx.Response(451, text="geo blocked")
        if path.startswith("/data/futures/um/monthly/fundingRate/"):
            return httpx.Response(200, content=funding_zip)
        if path.startswith("/data/futures/um/daily/markPriceKlines/"):
            return httpx.Response(200, content=mark_zip)
        if path.startswith("/data/spot/daily/klines/"):
            return httpx.Response(200, content=spot_zip)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_derivatives_rows(symbols=("BTCUSDT",), limit=2, client=client)

    assert len(result.rows) == 3
    assert any(
        row.to_warehouse_row()["source"].startswith(
            f"{DERIVATIVES_VENUE}.derivatives.binance_public_data."
        )
        for row in result.rows
    )
    assert any(
        attempt.source == "binance_api"
        and attempt.record_type == "funding_rate"
        and attempt.status == "failed"
        for attempt in result.source_attempts
    )
    assert any(
        attempt.source == "binance_public_data"
        and attempt.record_type == "funding_rate"
        and attempt.status == "success"
        and attempt.rows == 2
        for attempt in result.source_attempts
    )


@pytest.mark.asyncio
async def test_partial_success_writes_available_rows() -> None:
    funding_csv = "\n".join(
        [
            "calc_time,funding_interval_hours,last_funding_rate",
            "1700000000000,8,0.00010",
        ]
    )
    funding_zip = _zip_csv("BTCUSDT-fundingRate-2026-03.csv", funding_csv)

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        full_url = str(request.url)
        if full_url.startswith(BINANCE_FUNDING_RATE_URL):
            return httpx.Response(451, text="geo blocked")
        if full_url.startswith(BINANCE_MARK_PRICE_URL):
            return httpx.Response(451, text="geo blocked")
        if path.startswith("/data/futures/um/monthly/fundingRate/"):
            return httpx.Response(200, content=funding_zip)
        if path.startswith("/data/futures/um/daily/markPriceKlines/"):
            return httpx.Response(404)
        if path.startswith("/data/spot/daily/klines/"):
            return httpx.Response(404)
        if str(request.url).startswith(BINANCE_PUBLIC_DATA_BASE_URL):
            return httpx.Response(404)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_derivatives_rows(symbols=("BTCUSDT",), limit=1, client=client)

    assert len(result.rows) == 1
    assert result.rows[0].record_type == "funding_rate"
    assert any(
        attempt.record_type == "perp_basis" and attempt.status == "failed"
        for attempt in result.source_attempts
    )
    assert any("perp_basis" in error for error in result.errors)
