from __future__ import annotations

import json

from joint_research.research.wallet_flow_manifest_review_gate import run_wallet_flow_manifest_review_gate


def _write_manifest_json(path, *, rows, dry_run=True, manifest_rows=None) -> None:
    payload = {
        "manifest_id": "mfest",
        "coverage_csv": "coverage.csv",
        "dry_run": dry_run,
        "batch_size": 2,
        "max_batches": 1,
        "batches": 1,
        "manifest_rows": len(rows) if manifest_rows is None else manifest_rows,
        "thresholds": {
            "min_wallet_flow_rows": 24,
            "min_market_flow_hourly_rows": 24,
            "min_whale_flow_hourly_rows": 24,
        },
        "command_template": None,
        "rows": rows,
    }
    path.write_text(json.dumps(payload))


def test_valid_review_ready_manifest_passes(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "PASS"
    assert result.report_path is not None and result.report_path.exists()


def test_missing_file_fails(tmp_path) -> None:
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=tmp_path / "missing.json",
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_invalid_json_fails(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{not json")
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_review_required_rows_fail_by_default(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
            "command_status": "REVIEW_REQUIRED",
            "ingest_command": "REVIEW_REQUIRED: noop",
            "row_checksum": "c1",
        }
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_review_required_rows_pass_only_with_allow_review_required(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
            "command_status": "REVIEW_REQUIRED",
            "ingest_command": "REVIEW_REQUIRED: noop",
            "row_checksum": "c1",
        }
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=True,
        require_dry_run=True,
    )
    assert result.status == "PASS"


def test_duplicate_idempotency_keys_fail(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
        {
            "manifest_id": "mfest",
            "batch_id": 1,
            "rank": 1,
            "idempotency_key": "dup",
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
        },
        {
            "manifest_id": "mfest",
            "batch_id": 1,
            "rank": 2,
            "idempotency_key": "dup",
            "market_id": "m2",
            "market_slug": "s2",
            "asset": "ETH",
            "is_active": True,
            "priority_score": "1.0000",
            "reasons": "r",
            "action": "a",
            "command_status": "REVIEW_READY",
            "ingest_command": "echo safe",
            "row_checksum": "c2",
        },
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_duplicate_row_checksums_fail(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
            "row_checksum": "dup",
        },
        {
            "manifest_id": "mfest",
            "batch_id": 1,
            "rank": 2,
            "idempotency_key": "k2",
            "market_id": "m2",
            "market_slug": "s2",
            "asset": "ETH",
            "is_active": True,
            "priority_score": "1.0000",
            "reasons": "r",
            "action": "a",
            "command_status": "REVIEW_READY",
            "ingest_command": "echo safe",
            "row_checksum": "dup",
        },
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_unsafe_shell_operators_fail(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
            "ingest_command": "echo safe && echo nope",
            "row_checksum": "c1",
        }
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_require_dry_run_catches_false(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
    ]
    _write_manifest_json(manifest, rows=rows, dry_run=False)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.status == "FAIL"


def test_writer_creates_report(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    rows = [
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
    ]
    _write_manifest_json(manifest, rows=rows)
    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest,
        output_dir=tmp_path / "out",
        allow_review_required=False,
        require_dry_run=True,
    )
    assert result.report_path is not None
    report_text = result.report_path.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in report_text
    assert "No ingestion executed." in report_text

