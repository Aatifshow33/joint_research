from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli import app


def test_wallet_flow_backfill_batches_help() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "wallet-flow-backfill-batches", "--help"])

    assert result.exit_code == 0
    assert "--coverage-csv" in result.output
    assert "--output-dir" in result.output
    assert "--min-wallet-flow-rows" in result.output
    # Typer truncates long option names in help output ("--min-market-flow-hour…").
    assert "Minimum market-flow" in result.output
    assert "Minimum whale-flow" in result.output
    assert "--batch-size" in result.output
    assert "--max-batches" in result.output
    assert "--dry-run" in result.output


def test_wallet_flow_backfill_batches_cli_writes_artifacts(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    coverage_csv.write_text(
        "\n".join(
            [
                "market_id,market_slug,asset,is_active,is_closed,is_archived,volume_1mo_usd,volume_total_usd,wallet_flow_rows,trade_rows,copy_rows,market_flow_hourly_rows,whale_flow_hourly_rows",
                "m1,btc-market,BTC,True,False,False,1000,2000,0,0,0,0,0",
                "m2,eth-market,ETH,True,False,False,1000,2000,0,0,0,0,0",
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
            "wallet-flow-backfill-batches",
            "--coverage-csv",
            str(coverage_csv),
            "--output-dir",
            str(out_dir),
            "--batch-size",
            "1",
            "--max-batches",
            "2",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "dry_run=True" in result.output
    assert "batches=" in result.output
    assert "markets_planned=" in result.output
    assert "batch_size=1" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "batch_report=" in result.output
    assert "batch_csv=" in result.output
    assert (out_dir / "wallet_flow_backfill_batches.md").exists()
    assert (out_dir / "wallet_flow_backfill_batches.csv").exists()

