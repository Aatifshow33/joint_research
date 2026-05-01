from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli import app


def test_wallet_flow_backfill_priority_help() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "wallet-flow-backfill-priority", "--help"])

    assert result.exit_code == 0
    assert "--coverage-csv" in result.output
    assert "--min-wallet-flow-rows" in result.output
    assert "--min-market-flow-hourly-rows" in result.output
    assert "--min-whale-flow-hourly-rows" in result.output
    assert "--show-top" in result.output


def test_wallet_flow_backfill_priority_writes_artifacts(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    coverage_csv.write_text(
        "\n".join(
            [
                "market_id,market_slug,asset,is_active,is_closed,is_archived,volume_1mo_usd,volume_total_usd,wallet_flow_rows,trade_rows,copy_rows,market_flow_hourly_rows,whale_flow_hourly_rows",
                "m1,btc-market,BTC,True,False,False,1000,2000,0,0,0,0,0",
                "m2,eth-market,ETH,True,False,False,1000,2000,100,100,0,50,50",
            ]
        )
        + "\n"
    )

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-backfill-priority",
            "--coverage-csv",
            str(coverage_csv),
            "--output-dir",
            str(out_dir),
            "--min-wallet-flow-rows",
            "24",
            "--min-market-flow-hourly-rows",
            "24",
            "--min-whale-flow-hourly-rows",
            "24",
            "--show-top",
            "10",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "backfill_markets=" in result.output
    assert "active_backfill_markets=" in result.output
    assert "total_markets=" in result.output
    assert "priorities_rendered=" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "priority_report=" in result.output
    assert "priority_csv=" in result.output
    assert (out_dir / "wallet_flow_backfill_priority.md").exists()
    assert (out_dir / "wallet_flow_backfill_priority.csv").exists()

