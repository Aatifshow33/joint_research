from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli import app


def _write_coverage_csv(path) -> None:
    path.write_text(
        "\n".join(
            [
                "market_id,market_slug,asset,is_active,is_closed,is_archived,volume_1mo_usd,volume_total_usd,wallet_flow_rows,trade_rows,copy_rows,market_flow_hourly_rows,whale_flow_hourly_rows",
                "m1,btc-market,BTC,True,False,False,1000,2000,0,0,0,0,0",
                "m2,eth-market,ETH,True,False,False,1000,2000,0,0,0,0,0",
            ]
        )
        + "\n"
    )


def test_wallet_flow_approved_manifest_packet_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-approved-manifest-packet", "--help"])
    assert result.exit_code == 0
    assert "--manifest-json" in result.output
    assert "--review-gate-report" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_packet_and_prints_export_status_pass(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)
    out_dir = tmp_path / "out"
    runner = CliRunner()

    manifest_result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-backfill-manifest",
            "--coverage-csv",
            str(coverage_csv),
            "--output-dir",
            str(out_dir),
            "--batch-size",
            "1",
            "--max-batches",
            "2",
            "--dry-run",
            "--command-template-preset",
            "review_echo",
        ],
    )
    assert manifest_result.exit_code == 0, manifest_result.output

    gate_result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-manifest-review-gate",
            "--manifest-json",
            str(out_dir / "wallet_flow_backfill_execution_manifest.json"),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert gate_result.exit_code == 0, gate_result.output
    assert "gate_status=PASS" in gate_result.output

    packet_result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-approved-manifest-packet",
            "--manifest-json",
            str(out_dir / "wallet_flow_backfill_execution_manifest.json"),
            "--review-gate-report",
            str(out_dir / "wallet_flow_manifest_review_gate.md"),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert packet_result.exit_code == 0, packet_result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in packet_result.output
    assert "export_status=PASS" in packet_result.output
    assert "gate_status=PASS" in packet_result.output
    assert "manifest_rows=" in packet_result.output
    assert "No candidates promoted." in packet_result.output
    assert "No threshold changes." in packet_result.output
    assert "No live trading changes." in packet_result.output
    assert "No ingestion executed." in packet_result.output
    assert "approved_manifest_packet=" in packet_result.output
    assert "approved_manifest_packet_json=" in packet_result.output

    assert (out_dir / "wallet_flow_approved_manifest_packet.md").exists()
    assert (out_dir / "wallet_flow_approved_manifest_packet.json").exists()


def test_cli_blocked_when_manifest_missing(tmp_path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-approved-manifest-packet",
            "--manifest-json",
            str(tmp_path / "missing_manifest.json"),
            "--review-gate-report",
            str(tmp_path / "missing_gate.md"),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "export_status=BLOCKED" in result.output
    assert "gate_status=FAIL" in result.output
    assert "No ingestion executed." in result.output
    assert (out_dir / "wallet_flow_approved_manifest_packet.md").exists()
    assert (out_dir / "wallet_flow_approved_manifest_packet.json").exists()
