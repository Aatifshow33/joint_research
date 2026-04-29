from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli import app
from joint_research.ingest.crypto_derivatives import (
    DerivativesFetchResult,
    DerivativesRow,
    DerivativesSourceAttempt,
)


def test_cli_exits_zero_when_fallback_succeeds(monkeypatch, tmp_path) -> None:
    async def fake_fetch_derivatives_rows(*, symbols, limit, client=None):  # type: ignore[no-untyped-def]
        del symbols, limit, client
        row = DerivativesRow(
            venue="binance",
            record_type="funding_rate",
            symbol="BTCUSDT",
            event_time_ns=1_700_000_000_000 * 1_000_000,
            payload_hash="hash",
            payload_json="{}",
            funding_time_ns=1_700_000_000_000 * 1_000_000,
            funding_rate=0.0001,
            mark_price=30000.0,
            spot_price=None,
            basis_pct=None,
            source="binance.derivatives.binance_public_data.funding_rate",
        )
        return DerivativesFetchResult(
            rows=[row],
            errors=("BTCUSDT:funding_rate:binance_api:http_451",),
            source_attempts=(
                DerivativesSourceAttempt(
                    source="binance_api",
                    symbol="BTCUSDT",
                    record_type="funding_rate",
                    status="failed",
                    rows=0,
                    detail="http_451",
                ),
                DerivativesSourceAttempt(
                    source="binance_public_data",
                    symbol="BTCUSDT",
                    record_type="funding_rate",
                    status="success",
                    rows=1,
                ),
            ),
        )

    monkeypatch.setattr(
        "joint_research.ingest.crypto_derivatives.fetch_derivatives_rows",
        fake_fetch_derivatives_rows,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "crypto-derivatives",
            "--symbols",
            "BTCUSDT",
            "--limit",
            "1",
            "--warehouse-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "ingested=1" in result.stdout
    assert "source=binance_api" in result.stdout
    assert "status=failed" in result.stdout
    assert "source=binance_public_data" in result.stdout
    assert "status=success" in result.stdout
