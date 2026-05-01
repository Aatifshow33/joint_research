
from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli import app


def test_wallet_flow_coverage_gate_help() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "wallet-flow-coverage-gate", "--help"])

    assert result.exit_code == 0
    assert "--coverage-csv" in result.output
    assert "--min-covered-markets" in result.output


def test_wallet_flow_coverage_gate_writes_report(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    coverage_csv.write_text(
        "\n".join(
            [
                "market_id,market_slug,asset,is_active,is_closed,is_archived,volume_1mo_usd,volume_total_usd,wallet_flow_rows,trade_rows,copy_rows,market_flow_hourly_rows,whale_flow_hourly_rows",
                "m1,btc-market,BTC,True,False,False,1000,2000,100,100,2,50,50",
                "m2,eth-market,ETH,True,False,False,1000,2000,80,80,0,40,40",
            ]
        )
        + "\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-coverage-gate",
            "--coverage-csv",
            str(coverage_csv),
            "--output-dir",
            str(tmp_path / "out"),
            "--min-covered-markets",
            "2",
            "--min-coverage-ratio",
            "0.50",
            "--min-total-wallet-flow-rows",
            "100",
            "--min-market-flow-hourly-rows",
            "80",
            "--min-whale-flow-hourly-rows",
            "80",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "gate_status=PASS" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert (tmp_path / "out" / "wallet_flow_coverage_gate.md").exists()
