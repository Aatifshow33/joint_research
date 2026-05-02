from __future__ import annotations

import json

from joint_research.research.wallet_flow_dry_run_execution_planner import (
    build_wallet_flow_dry_run_execution_plan,
    write_wallet_flow_dry_run_execution_plan,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _manifest_payload(*, rows: int = 2) -> dict:
    return {
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "ingest_command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _approved_payload(*, export_status: str) -> dict:
    return {
        "export_status": export_status,
        "gate_status": "PASS" if export_status == "PASS" else "FAIL",
        "manifest_rows": 2,
    }


def _audit_payload(*, audit_status: str) -> dict:
    return {
        "audit_status": audit_status,
        "reports_found": 1,
        "reports_missing": 0,
    }


def test_pass_approved_and_ready_audit_yields_ready_plan(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=2))
    _write_json(approved_json, _approved_payload(export_status="PASS"))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert plan.plan_status == "READY"
    assert plan.approved_packet_status == "PASS"
    assert plan.audit_status == "READY"


def test_missing_approved_packet_yields_blocked_plan(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=tmp_path / "missing-approved.json",
        audit_index_json=audit_json,
    )

    assert plan.plan_status == "BLOCKED"
    assert plan.approved_packet_status == "MISSING"


def test_missing_audit_index_yields_blocked_plan(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(approved_json, _approved_payload(export_status="PASS"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=tmp_path / "missing-audit.json",
    )

    assert plan.plan_status == "BLOCKED"
    assert plan.audit_status == "MISSING"


def test_blocked_approved_packet_yields_blocked_plan(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(approved_json, _approved_payload(export_status="BLOCKED"))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert plan.plan_status == "BLOCKED"
    assert plan.approved_packet_status == "BLOCKED"


def test_blocked_audit_index_yields_blocked_plan(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(approved_json, _approved_payload(export_status="PASS"))
    _write_json(audit_json, _audit_payload(audit_status="BLOCKED"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert plan.plan_status == "BLOCKED"
    assert plan.audit_status == "BLOCKED"


def test_invalid_json_produces_blocked_plan_with_warning(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    approved_json.write_text("{not json")
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert plan.plan_status == "BLOCKED"
    assert plan.approved_packet_status == "INVALID"
    assert any("approved_packet_json_invalid" in warning for warning in plan.warnings)


def test_plan_includes_no_execution_and_dry_run_and_mode(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(approved_json, _approved_payload(export_status="PASS"))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert plan.no_execution is True
    assert plan.dry_run is True
    assert plan.execution_mode == "preview_only"


def test_first_ten_planned_rows_include_command(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=12))
    _write_json(approved_json, _approved_payload(export_status="PASS"))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    plan = build_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
    )

    assert len(plan.planned_rows) == 10
    assert all(row.command.startswith("review_wallet_flow_backfill") for row in plan.planned_rows)


def test_safety_copy_is_included(tmp_path) -> None:
    manifest_json = tmp_path / "manifest.json"
    approved_json = tmp_path / "approved.json"
    audit_json = tmp_path / "audit.json"
    _write_json(manifest_json, _manifest_payload(rows=1))
    _write_json(approved_json, _approved_payload(export_status="PASS"))
    _write_json(audit_json, _audit_payload(audit_status="READY"))

    artifacts = write_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json,
        approved_packet_json=approved_json,
        audit_index_json=audit_json,
        output_dir=tmp_path / "out",
    )
    text = artifacts.plan_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Dry-run execution plan only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "Approved for human review only." in text
