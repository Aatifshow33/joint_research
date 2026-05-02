from __future__ import annotations

import json

from joint_research.research.wallet_flow_operator_approval_ledger import (
    build_wallet_flow_operator_approval_ledger,
    write_wallet_flow_operator_approval_ledger,
)


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _handoff_payload(*, handoff_status: str = "READY_FOR_MANUAL_APPROVAL", rows: int = 2) -> dict:
    return {
        "handoff_status": handoff_status,
        "plan_status": "READY",
        "approved_packet_status": "PASS",
        "audit_status": "READY",
        "manifest_id": "mfest-1",
        "manifest_rows": rows,
        "planned_row_count": rows,
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


def test_ready_handoff_default_pending_yields_pending_manual_review(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL"))

    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="pending",
        reviewer="",
        review_note="",
    )

    assert ledger.ledger_status == "PENDING_MANUAL_REVIEW"


def test_ready_handoff_approve_yields_approved(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL"))

    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="approve",
        reviewer="operator",
        review_note="approved for local review only",
    )

    assert ledger.ledger_status == "APPROVED"


def test_ready_handoff_reject_yields_rejected(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL"))

    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="reject",
        reviewer="operator",
        review_note="reject",
    )

    assert ledger.ledger_status == "REJECTED"


def test_missing_handoff_yields_blocked(tmp_path) -> None:
    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=tmp_path / "missing-handoff.json",
        decision="pending",
        reviewer="",
        review_note="",
    )

    assert ledger.ledger_status == "BLOCKED"
    assert ledger.handoff_status == "MISSING"


def test_invalid_handoff_json_yields_blocked_with_warning(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    handoff_json.write_text("{not json")

    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="pending",
        reviewer="",
        review_note="",
    )

    assert ledger.ledger_status == "BLOCKED"
    assert ledger.handoff_status == "INVALID"
    assert any("guarded_handoff_json_invalid" in warning for warning in ledger.warnings)


def test_blocked_handoff_yields_blocked(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="BLOCKED"))

    ledger = build_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="approve",
        reviewer="operator",
        review_note="attempted approve",
    )

    assert ledger.ledger_status == "BLOCKED"
    assert ledger.handoff_status == "BLOCKED"


def test_ledger_flags_and_mode(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL"))

    artifacts = write_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="pending",
        reviewer="manual-operator",
        review_note="Phase 4.22 validation only",
        output_dir=tmp_path / "out",
    )

    ledger = artifacts.ledger
    assert ledger.approval_required is True
    assert ledger.manual_operator_only is True
    assert ledger.no_execution is True
    assert ledger.execution_mode == "approval_ledger_only"


def test_first_ten_rows_include_command_and_safety_copy(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL", rows=12))

    artifacts = write_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=handoff_json,
        decision="pending",
        reviewer="",
        review_note="",
        output_dir=tmp_path / "out",
    )

    assert len(artifacts.ledger.planned_rows) == 10
    assert all(
        row.command.startswith("review_wallet_flow_backfill")
        for row in artifacts.ledger.planned_rows
    )

    text = artifacts.ledger_md.read_text()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "No candidates promoted." in text
    assert "No threshold changes." in text
    assert "No live trading changes." in text
    assert "Operator approval ledger only." in text
    assert "No ingestion executed." in text
    assert "No manifest commands executed." in text
    assert "No live execution adapter enabled." in text
    assert "Ledger records review decision only." in text


def test_invalid_decision_raises(tmp_path) -> None:
    handoff_json = tmp_path / "handoff.json"
    _write_json(handoff_json, _handoff_payload(handoff_status="READY_FOR_MANUAL_APPROVAL"))

    try:
        build_wallet_flow_operator_approval_ledger(
            guarded_handoff_json=handoff_json,
            decision="ship",
            reviewer="",
            review_note="",
        )
    except ValueError as exc:
        assert "decision must be one of" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid decision")
