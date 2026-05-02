from __future__ import annotations

import json

from typer.testing import CliRunner

from joint_research.cli import app


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_wallet_flow_dry_run_execution_planner_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-dry-run-execution-planner", "--help"])

    assert result.exit_code == 0
    assert "--manifest-json" in result.output
    assert "--approved-packet-json" in result.output
    assert "--audit-index-json" in result.output
    assert "--output-dir" in result.output


def test_cli_writes_markdown_and_json_and_prints_status(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    out_dir = tmp_path / "out"

    _write_json(
        manifest_json,
        {
            "manifest_id": "mfest-1",
            "manifest_rows": 1,
            "rows": [
                {
                    "batch_id": 1,
                    "rank": 1,
                    "asset": "BTC",
                    "market_id": "m1",
                    "market_slug": "market-1",
                    "command_status": "REVIEW_READY",
                    "idempotency_key": "k1",
                    "row_checksum": "c1",
                    "ingest_command": "review_wallet_flow_backfill market_id=m1",
                }
            ],
        },
    )
    _write_json(
        approved_json,
        {
            "export_status": "PASS",
            "gate_status": "PASS",
            "manifest_rows": 1,
        },
    )
    _write_json(
        audit_json,
        {
            "audit_status": "READY",
            "reports_found": 1,
            "reports_missing": 0,
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-dry-run-execution-planner",
            "--manifest-json",
            str(manifest_json),
            "--approved-packet-json",
            str(approved_json),
            "--audit-index-json",
            str(audit_json),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert "plan_status=READY" in result.output
    assert "manifest_rows=1" in result.output
    assert "approved_packet_status=PASS" in result.output
    assert "audit_status=READY" in result.output
    assert "No candidates promoted." in result.output
    assert "No threshold changes." in result.output
    assert "No live trading changes." in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
    assert "dry_run_execution_plan=" in result.output
    assert "dry_run_execution_plan_json=" in result.output

    assert (out_dir / "wallet_flow_dry_run_execution_plan.md").exists()
    assert (out_dir / "wallet_flow_dry_run_execution_plan.json").exists()


def test_cli_blocked_when_inputs_missing(tmp_path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-dry-run-execution-planner",
            "--manifest-json",
            str(tmp_path / "missing-manifest.json"),
            "--approved-packet-json",
            str(tmp_path / "missing-approved.json"),
            "--audit-index-json",
            str(tmp_path / "missing-audit.json"),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "plan_status=BLOCKED" in result.output
    assert "approved_packet_status=MISSING" in result.output
    assert "audit_status=MISSING" in result.output
    assert "No ingestion executed." in result.output
    assert "No manifest commands executed." in result.output
