from __future__ import annotations

import json

import duckdb
import pytest
from joint_research.ingest.crypto_derivatives import (
    DERIVATIVES_VENUE,
    classify_derivatives_regime,
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
