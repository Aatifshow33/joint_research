
from __future__ import annotations

from pathlib import Path

from joint_research.research.wallet_flow_coverage_gate import (
    WalletFlowCoverageGateThresholds,
    read_wallet_flow_coverage_rows,
    render_wallet_flow_coverage_gate,
    run_wallet_flow_coverage_gate,
    write_wallet_flow_coverage_gate_report,
)


def _write_coverage_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "market_id,market_slug,asset,is_active,is_closed,is_archived,volume_1mo_usd,volume_total_usd,wallet_flow_rows,trade_rows,copy_rows,market_flow_hourly_rows,whale_flow_hourly_rows",
                "m1,btc-market,BTC,True,False,False,1000,2000,100,100,2,50,50",
                "m2,eth-market,ETH,True,False,False,1000,2000,80,80,0,40,40",
                "m3,xrp-market,XRP,True,False,False,1000,2000,0,0,0,0,0",
            ]
        )
        + "\n"
    )


def test_read_wallet_flow_coverage_rows(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)

    rows = read_wallet_flow_coverage_rows(coverage_csv)

    assert len(rows) == 3
    assert rows[0].market_id == "m1"
    assert rows[0].has_wallet_flow is True
    assert rows[2].has_wallet_flow is False


def test_coverage_gate_passes_when_thresholds_met(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)

    gate = run_wallet_flow_coverage_gate(
        coverage_csv=coverage_csv,
        thresholds=WalletFlowCoverageGateThresholds(
            min_covered_markets=2,
            min_coverage_ratio=0.50,
            min_total_wallet_flow_rows=100,
            min_market_flow_hourly_rows=80,
            min_whale_flow_hourly_rows=80,
        ),
    )

    assert gate.status == "PASS"
    assert gate.covered_markets == 2
    assert gate.total_markets == 3
    assert gate.total_wallet_flow_rows == 180
    assert gate.failure_reasons == []


def test_coverage_gate_fails_when_thresholds_not_met(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)

    gate = run_wallet_flow_coverage_gate(
        coverage_csv=coverage_csv,
        thresholds=WalletFlowCoverageGateThresholds(
            min_covered_markets=5,
            min_coverage_ratio=0.90,
            min_total_wallet_flow_rows=1000,
            min_market_flow_hourly_rows=500,
            min_whale_flow_hourly_rows=500,
        ),
    )

    assert gate.status == "FAIL"
    assert "covered markets below minimum" in gate.failure_reasons
    assert "coverage ratio below minimum" in gate.failure_reasons
    assert "wallet-flow rows below minimum" in gate.failure_reasons


def test_coverage_gate_missing_csv_is_fail(tmp_path) -> None:
    coverage_csv = tmp_path / "missing.csv"

    gate = run_wallet_flow_coverage_gate(
        coverage_csv=coverage_csv,
        thresholds=WalletFlowCoverageGateThresholds(),
    )

    assert gate.status == "FAIL"
    assert gate.missing_coverage_csv is True
    assert "coverage csv missing" in gate.failure_reasons


def test_coverage_gate_report_keeps_non_tradeable_copy(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)

    report_path, gate = write_wallet_flow_coverage_gate_report(
        coverage_csv=coverage_csv,
        output_dir=tmp_path / "out",
        thresholds=WalletFlowCoverageGateThresholds(
            min_covered_markets=2,
            min_coverage_ratio=0.50,
            min_total_wallet_flow_rows=100,
            min_market_flow_hourly_rows=80,
            min_whale_flow_hourly_rows=80,
        ),
    )
    rendered = render_wallet_flow_coverage_gate(
        gate,
        WalletFlowCoverageGateThresholds(
            min_covered_markets=2,
            min_coverage_ratio=0.50,
            min_total_wallet_flow_rows=100,
            min_market_flow_hourly_rows=80,
            min_whale_flow_hourly_rows=80,
        ),
    )

    assert report_path.name == "wallet_flow_coverage_gate.md"
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in rendered
    assert "No candidates promoted." in rendered
    assert "No threshold changes." in rendered
    assert "No live trading changes." in rendered
