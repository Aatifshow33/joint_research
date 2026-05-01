from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def test_wallet_flow_manifest_review_gate_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-manifest-review-gate", "--help"])
    assert result.exit_code == 0
    assert "--manifest-json" in result.output
    assert "--output-dir" in result.output
    # Typer truncates long option names in help output ("--allow-review-requi…").
    assert "Permit" in result.output
    assert "REVIEW_REQUIRED" in result.output
    assert "--require-dry-run" in result.output


def test_wallet_flow_manifest_review_gate_writes_report(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_id": "mfest",
                "coverage_csv": "coverage.csv",
                "dry_run": True,
                "batch_size": 1,
                "max_batches": 1,
                "batches": 1,
                "manifest_rows": 1,
                "thresholds": {
                    "min_wallet_flow_rows": 24,
                    "min_market_flow_hourly_rows": 24,
                    "min_whale_flow_hourly_rows": 24,
                },
                "command_template": "echo {market_id}",
                "rows": [
                    {
                        "manifest_id": "mfest",
                        "batch_id": 1,
                        "rank": 1,
                        "idempotency_key": "k1",
                        "market_id": "m1",
                        "market_slug": "s1",
                        "asset": "BTC",
                        "is_active": True,
                        "priority_score": "1.0000",
                        "reasons": "r",
                        "action": "a",
                        "command_status": "REVIEW_READY",
                        "ingest_command": "echo safe",
                        "row_checksum": "c1",
                    }
                ],
            }
        )
    )

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-manifest-review-gate",
            "--manifest-json",
            str(manifest),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "gate_status=PASS" in result.output
    assert "No ingestion executed." in result.output
    assert "review_gate_report=" in result.output
    assert (out_dir / "wallet_flow_manifest_review_gate.md").exists()

