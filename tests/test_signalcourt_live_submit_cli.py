from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from joint_research.cli import app
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config


REPO_ROOT = Path(__file__).resolve().parents[1]

DERIVATIVES_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/derivatives_regime"
DERIVATIVES_RESULTS_CSV = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_results.csv"
DERIVATIVES_CANDIDATES_JSON = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_candidates.json"
DERIVATIVES_SUMMARY_MD = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_summary.md"

WALLET_FLOW_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/wallet_flow_signal"
WALLET_FLOW_SIGNAL_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_summary.md"
WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV = (
    WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_diagnostics.csv"
)
WALLET_FLOW_REJECTION_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_summary.md"

_ARTIFACT_INPUTS = (
    DERIVATIVES_RESULTS_CSV,
    DERIVATIVES_CANDIDATES_JSON,
    DERIVATIVES_SUMMARY_MD,
    WALLET_FLOW_SIGNAL_SUMMARY_MD,
    WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
    WALLET_FLOW_REJECTION_SUMMARY_MD,
)


def _invoke_live_submit(*, lane: str, extra: list[str] | None = None):
    runner = CliRunner()
    cmd = [
        "signalcourt",
        "live-submit",
        "--lane",
        lane,
        "--symbol",
        "ETHUSD",
        "--side",
        "BUY",
        "--quantity",
        "0.02",
        "--limit-price",
        "200",
        "--notional-usd",
        "2",
        "--venue",
        "paper_local",
        "--order-type",
        "limit",
        "--approval-packet-id",
        "approval_packet_test_001",
    ]
    if extra:
        cmd.extend(extra)
    return runner.invoke(app, cmd)


def test_live_submit_command_exists() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    assert result.exit_code == 0, result.output


def test_command_requires_explicit_inputs() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["signalcourt", "live-submit", "--lane", "wallet-flow"])
    assert result.exit_code != 0


def test_command_requires_confirm_live() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--operator-acknowledgement"],
    )
    assert result.exit_code != 0
    assert "--confirm-live" in result.output


def test_command_requires_operator_acknowledgement() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live"],
    )
    assert result.exit_code != 0
    assert "--operator-acknowledgement" in result.output


def test_output_is_deterministic_json() -> None:
    first = _invoke_live_submit(
        lane="derivatives-regime",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    second = _invoke_live_submit(
        lane="derivatives-regime",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_payload = json.loads(first.output)
    second_payload = json.loads(second.output)
    assert first_payload == second_payload


def test_output_has_live_transport_disabled_status() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["transport_status"] == "LIVE_TRANSPORT_DISABLED"


def test_output_has_live_submit_available_false() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["live_submit_available"] is False


def test_output_has_order_submitted_false() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["order_submitted"] is False


def test_output_has_broker_exchange_flags_false() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["broker_call_performed"] is False
    assert payload["exchange_call_performed"] is False


def test_output_has_live_and_micro_live_execution_flags_false() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["live_execution_allowed"] is False
    assert payload["micro_live_execution_allowed"] is False


def test_output_includes_approval_packet_id() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["approval_packet_id"] == "approval_packet_test_001"


def test_output_includes_blocked_reasons_and_required_next_gates() -> None:
    result = _invoke_live_submit(
        lane="derivatives-regime",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["blocked_reasons"]
    assert payload["required_next_gates"]


def test_output_includes_non_authorization_notice() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    lowered = payload["non_authorization_notice"].lower()
    assert "does not authorize" in lowered or "hard-disabled" in lowered


def test_output_contains_no_broker_exchange_credential_fields() -> None:
    result = _invoke_live_submit(
        lane="derivatives-regime",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload_text = result.output.lower()
    forbidden = [
        "api_key",
        "secret_key",
        "private_key",
        "broker_token",
        "exchange_token",
        "access_token",
    ]
    for token in forbidden:
        assert token not in payload_text


def test_command_does_not_create_artifacts(tmp_path: Path, monkeypatch) -> None:
    before_artifacts = {path: path.read_bytes() for path in _ARTIFACT_INPUTS}
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "signalcourt",
            "live-submit",
            "--lane",
            "wallet-flow",
            "--symbol",
            "BTCUSD",
            "--side",
            "BUY",
            "--quantity",
            "0.01",
            "--limit-price",
            "100",
            "--notional-usd",
            "1",
            "--venue",
            "paper_local",
            "--order-type",
            "limit",
            "--approval-packet-id",
            "approval_packet_tmp_001",
            "--confirm-live",
            "--operator-acknowledgement",
        ],
    )
    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []
    after_artifacts = {path: path.read_bytes() for path in _ARTIFACT_INPUTS}
    assert after_artifacts == before_artifacts


def test_wallet_flow_path_remains_non_executable() -> None:
    result = _invoke_live_submit(
        lane="wallet-flow",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["lane"] == "wallet-flow"
    assert payload["pipeline_allows_order"] is False
    assert payload["order_submitted"] is False
    assert payload["live_execution_allowed"] is False


def test_derivatives_path_remains_non_executable() -> None:
    result = _invoke_live_submit(
        lane="derivatives-regime",
        extra=["--confirm-live", "--operator-acknowledgement"],
    )
    payload = json.loads(result.output)
    assert payload["lane"] == "derivatives-regime"
    assert payload["pipeline_allows_order"] is False
    assert payload["order_submitted"] is False
    assert payload["live_execution_allowed"] is False


def test_golden_blocked_no_execution_behavior_remains_unchanged() -> None:
    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
