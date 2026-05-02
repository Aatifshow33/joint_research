from __future__ import annotations

import json

from joint_research.research.wallet_flow_guarded_operator_handoff import (
    build_wallet_flow_guarded_operator_handoff,
    write_wallet_flow_guarded_operator_handoff,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _dry_run_plan_payload(*, plan_status: str = "READY", rows: int = 2) -> dict:
    return {
        "plan_status": plan_status,
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "batch_count": 1,
        "command_status_counts": [{"command_status": "REVIEW_READY", "count": rows}],
        "planned_rows": [
            {
                "batch_id": 1,
                "rank": i + 1,
                "asset": "BTC",
                "market_id": f"m{i+1}",
                "market_slug": f"market-{i+1}",
                "command_status": "REVIEW_READY",
                "idempotency_key": f"k{i+1}",
                "row_checksum": f"c{i+1}",
                "command": f"review_wallet_flow_backfill market_id=m{i+1}",
            }
            for i in range(rows)
        ],
    }


def _approved_payload(*, export_status: str = "PASS") -> dict:
    return {
        "export_status": export_status,
        "gate_status": "PASS" if export_status == "PASS" else "FAIL",
        "manifest_rows": 2,
    }


def _audit_payload(*, audit_status: str = "READY") -> dict:
    return {
        "audit_status": audit_status,
        "reports_found": 1,
        "reports_missing": 0,
    }


def test_ready_inputs_yield_ready_for_manual_approval(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "READY_FOR_MANUAL_APPROVAL"


def test_missing_dry_run_plan_yields_blocked(tmp_path) -> None:
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=tmp_path / "missing-plan.json",
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.plan_status == "MISSING"


def test_missing_approved_packet_yields_blocked(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=tmp_path / "missing-approved.json",
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.approved_packet_status == "MISSING"


def test_missing_audit_index_yields_blocked(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=tmp_path / "missing-audit.json",
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.audit_status == "MISSING"


def test_blocked_dry_run_plan_yields_blocked(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="BLOCKED"))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.plan_status == "BLOCKED"


def test_blocked_approved_packet_yields_blocked(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(approved_packet_json, _approved_payload(export_status="BLOCKED"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.approved_packet_status == "BLOCKED"


def test_blocked_audit_index_yields_blocked(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="BLOCKED"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.audit_status == "BLOCKED"


def test_invalid_json_yields_blocked_with_warning(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    approved_packet_json.write_text("{not json")
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    handoff = build_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
    )

    assert handoff.handoff_status == "BLOCKED"
    assert handoff.approved_packet_status == "INVALID"
    assert any("approved_packet_json_invalid" in warning for warning in handoff.warnings)


def test_handoff_flags_and_mode_and_checklist(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY"))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    artifacts = write_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
        output_dir=tmp_path / "out",
    )

    handoff = artifacts.handoff
    assert handoff.approval_required is True
    assert handoff.manual_operator_only is True
    assert handoff.no_execution is True
    assert handoff.execution_mode == "manual_review_only"

    text = artifacts.handoff_md.read_text()
    assert "Confirm source market coverage is acceptable." in text
    assert "Confirm command template is review-only." in text
    assert "Confirm manifest review gate is PASS." in text
    assert "Confirm approved packet export_status is PASS." in text
    assert "Confirm audit_status is READY." in text
    assert "Confirm no live execution adapter is enabled." in text
    assert "Confirm no ingestion has been executed." in text


def test_first_ten_rows_include_command_and_safety_copy(tmp_path) -> None:
    dry_run_plan_json = tmp_path / "plan.json"
    approved_packet_json = tmp_path / "approved.json"
    audit_index_json = tmp_path / "audit.json"
    _write_json(dry_run_plan_json, _dry_run_plan_payload(plan_status="READY", rows=12))
    _write_json(approved_packet_json, _approved_payload(export_status="PASS"))
    _write_json(audit_index_json, _audit_payload(audit_status="READY"))

    artifacts = write_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json,
        approved_packet_json=approved_packet_json,
        audit_index_json=audit_index_json,
        output_dir=tmp_path / "out",
    )

    assert len(artifacts.handoff.planned_rows) == 10
    assert all(row.command.startswith("review_wallet_flow_backfill") for row in artifacts.handoff.planned_rows)

    text = artifacts.handoff_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Guarded operator handoff only." in text
    assert "Manual approval required." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "Approved for human review only." in text
