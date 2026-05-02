from __future__ import annotations

import hashlib
import json

from joint_research.research.wallet_flow_manifest_audit_index import (
    build_wallet_flow_manifest_audit_index,
    write_wallet_flow_manifest_audit_index,
)


def _default_paths(tmp_path):
    base = tmp_path / "audit"
    return {
        "output_dir": base,
        "coverage_gate_report": base / "wallet_flow_coverage_gate.md",
        "priority_report": base / "wallet_flow_backfill_priority.md",
        "batch_report": base / "wallet_flow_backfill_batches.md",
        "manifest_report": base / "wallet_flow_backfill_execution_manifest.md",
        "review_gate_report": base / "wallet_flow_manifest_review_gate.md",
        "approved_packet_report": base / "wallet_flow_approved_manifest_packet.md",
        "manifest_json": base / "wallet_flow_backfill_execution_manifest.json",
        "approved_packet_json": base / "wallet_flow_approved_manifest_packet.json",
    }


def _write_text(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_manifest_json(path, *, command_status="REVIEW_READY") -> None:
    _write_text(
        path,
        json.dumps(
            {
                "manifest_id": "mfest-1",
                "manifest_rows": 2,
                "dry_run": True,
                "rows": [
                    {
                        "batch_id": 1,
                        "rank": 1,
                        "asset": "BTC",
                        "market_id": "m1",
                        "market_slug": "market-1",
                        "command_status": command_status,
                        "idempotency_key": "k1",
                        "row_checksum": "c1",
                    },
                    {
                        "batch_id": 1,
                        "rank": 2,
                        "asset": "ETH",
                        "market_id": "m2",
                        "market_slug": "market-2",
                        "command_status": command_status,
                        "idempotency_key": "k2",
                        "row_checksum": "c2",
                    },
                ],
            }
        ),
    )


def _write_approved_packet_json(path, *, export_status: str) -> None:
    _write_text(
        path,
        json.dumps(
            {
                "export_status": export_status,
                "gate_status": "PASS" if export_status == "PASS" else "FAIL",
                "manifest_rows": 2,
            }
        ),
    )


def test_writes_markdown_and_json_index(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    _write_manifest_json(paths["manifest_json"])
    _write_approved_packet_json(paths["approved_packet_json"], export_status="PASS")

    artifacts = write_wallet_flow_manifest_audit_index(**paths)

    assert artifacts.audit_index_md.exists()
    assert artifacts.audit_index_json.exists()


def test_missing_reports_do_not_crash(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    artifacts = write_wallet_flow_manifest_audit_index(**paths)
    assert artifacts.index.audit_status == "BLOCKED"
    assert artifacts.index.reports_missing > 0


def test_report_hashes_are_deterministic(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    text = "hello-audit\n"
    _write_text(paths["priority_report"], text)
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()

    first = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})
    second = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})

    by_name_1 = {row.report_name: row for row in first.reports}
    by_name_2 = {row.report_name: row for row in second.reports}
    assert by_name_1["priority_report"].sha256 == expected
    assert by_name_1["priority_report"].sha256 == by_name_2["priority_report"].sha256


def test_valid_manifest_json_summary_is_included(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    _write_manifest_json(paths["manifest_json"], command_status="REVIEW_READY")
    _write_approved_packet_json(paths["approved_packet_json"], export_status="PASS")

    index = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})

    assert index.manifest_json_summary is not None
    assert index.manifest_json_summary.manifest_id == "mfest-1"
    assert index.manifest_json_summary.manifest_rows == 2
    assert index.manifest_json_summary.dry_run is True
    assert index.manifest_json_summary.command_status_counts == [("REVIEW_READY", 2)]
    assert index.manifest_json_summary.unique_idempotency_keys == 2
    assert index.manifest_json_summary.unique_row_checksums == 2


def test_invalid_manifest_json_produces_warning(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    _write_text(paths["manifest_json"], "{not json")

    index = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})

    assert index.manifest_json_summary is None
    assert any("manifest_json_invalid_json" in warning for warning in index.warnings)


def test_approved_packet_pass_yields_ready_status(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    _write_approved_packet_json(paths["approved_packet_json"], export_status="PASS")

    index = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})

    assert index.audit_status == "READY"
    assert index.recommendation == "Ready for human review of approved packet."


def test_missing_or_blocked_approved_packet_yields_blocked_status(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    missing = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})
    assert missing.audit_status == "BLOCKED"

    _write_approved_packet_json(paths["approved_packet_json"], export_status="BLOCKED")
    blocked = build_wallet_flow_manifest_audit_index(**{k: v for k, v in paths.items() if k != "output_dir"})
    assert blocked.audit_status == "BLOCKED"


def test_safety_copy_included(tmp_path) -> None:
    paths = _default_paths(tmp_path)
    _write_approved_packet_json(paths["approved_packet_json"], export_status="PASS")

    artifacts = write_wallet_flow_manifest_audit_index(**paths)
    text = artifacts.audit_index_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Audit index only." in text
    assert "No ingestion executed." in text
