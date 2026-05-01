"""CLI coverage for the wallet-flow diagnostic report flag."""

from __future__ import annotations

from typer.testing import CliRunner

from joint_research.cli_integrated import app


def test_wallet_flow_signal_help_exposes_diagnostic_report_flag() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "wallet-flow-signal", "--help"])

    assert result.exit_code == 0
    assert "--diagnostic-report" in result.output
    assert "--diagnostic-near-miss-limit" in result.output
    assert "wallet_flow_diagnostic_triage.md" in result.output
