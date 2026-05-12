from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from joint_research.cli import app


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


def test_signalcourt_dashboard_summary_cli_outputs_expected_sections() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["signalcourt", "dashboard-summary"])

    assert result.exit_code == 0, result.output
    lowered = result.output.lower()
    assert "signalcourt trader" in lowered
    assert "wallet-flow" in lowered
    assert "derivatives-regime" in lowered
    assert "no live trading" in lowered
    assert "no executable paper orders" in lowered or "blocked" in lowered
    assert "research-only" in lowered or "blocked" in lowered
    assert "non-authorization notice" in lowered


def test_signalcourt_dashboard_summary_cli_writes_no_files_and_modifies_no_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    before_artifacts = {path: path.read_bytes() for path in _ARTIFACT_INPUTS}

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["signalcourt", "dashboard-summary"])

    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []

    after_artifacts = {path: path.read_bytes() for path in _ARTIFACT_INPUTS}
    assert after_artifacts == before_artifacts
