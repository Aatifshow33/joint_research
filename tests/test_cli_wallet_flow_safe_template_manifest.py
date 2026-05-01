from __future__ import annotations

import json

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


def test_wallet_flow_backfill_manifest_help_includes_command_template_preset() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-backfill-manifest", "--help"])
    assert result.exit_code == 0
    assert "--command-template-pre" in result.output
    assert "review_ech" in result.output


def test_command_template_and_preset_are_mutually_exclusive(tmp_path) -> None:
    coverage_csv = tmp_path / "wallet_flow_coverage.csv"
    _write_coverage_csv(coverage_csv)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-backfill-manifest",
            "--coverage-csv",
            str(coverage_csv),
            "--output-dir",
            str(tmp_path / "out"),
            "--command-template",
            "echo {market_id}",
            "--command-template-preset",
            "review_echo",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid value for --command-template-preset" in result.output
    assert "Provide only one of" in result.output


def test_cli_can_generate_review_echo_manifest_and_pass_gate(tmp_path) -> None:
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
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in manifest_result.output
    assert "No candidates promoted." in manifest_result.output
    assert "No threshold changes." in manifest_result.output
    assert "No live trading changes." in manifest_result.output
    assert "No ingestion executed." in manifest_result.output

    manifest_json = out_dir / "wallet_flow_backfill_execution_manifest.json"
    payload = json.loads(manifest_json.read_text())
    assert payload["rows"]
    assert all(row["command_status"] == "REVIEW_READY" for row in payload["rows"])
    assert all("review_wallet_flow_backfill" in row["ingest_command"] for row in payload["rows"])

    gate_result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-manifest-review-gate",
            "--manifest-json",
            str(manifest_json),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert gate_result.exit_code == 0, gate_result.output
    assert "gate_status=PASS" in gate_result.output
    assert "No ingestion executed." in gate_result.output
