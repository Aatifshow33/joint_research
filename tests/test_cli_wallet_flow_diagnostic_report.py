from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from joint_research.cli import app
from joint_research.research import wallet_flow_diagnostic_triage as triage_module
from joint_research.research import wallet_flow_signal as signal_module


def test_wallet_flow_signal_help_includes_diagnostic_report_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "wallet-flow-signal", "--help"])

    assert result.exit_code == 0
    assert "--diagnostic-report" in result.output
    assert "--promotion-plan" in result.output


def test_wallet_flow_signal_diagnostic_report_writes_triage(
    monkeypatch, tmp_path
) -> None:
    calls: dict[str, object] = {}

    def fake_run_wallet_flow_signal_study_with_details(**kwargs):
        calls["run_kwargs"] = kwargs
        return SimpleNamespace(results=[], raw_results=[])

    def fake_write_wallet_flow_signal_report(*, output_dir, results, study_details):
        calls["signal_output_dir"] = output_dir
        return SimpleNamespace(
            summary_md=output_dir / "wallet_flow_signal_summary.md",
            results_csv=output_dir / "wallet_flow_signal_results.csv",
            candidates_json=output_dir / "wallet_flow_signal_candidates.json",
        )

    def fake_build_wallet_flow_rejection_diagnostics(*, raw_results, final_results):
        calls["raw_results"] = raw_results
        calls["final_results"] = final_results
        return ["diagnostic"]

    def fake_write_wallet_flow_diagnostic_triage_report(*, output_dir, diagnostics):
        calls["triage_output_dir"] = output_dir
        calls["diagnostics"] = diagnostics
        report_path = output_dir / "wallet_flow_diagnostic_triage.md"
        report_path.write_text("EXPLORATORY ONLY - NOT TRADEABLE\n")
        return report_path

    def fake_write_wallet_flow_promotion_plan_report(*, output_dir, diagnostics):
        calls["promotion_output_dir"] = output_dir
        calls["promotion_diagnostics"] = diagnostics
        report_path = output_dir / "wallet_flow_promotion_plan.md"
        report_path.write_text("EXPLORATORY ONLY - NOT TRADEABLE\n")
        return report_path

    monkeypatch.setattr(
        signal_module,
        "run_wallet_flow_signal_study_with_details",
        fake_run_wallet_flow_signal_study_with_details,
    )
    monkeypatch.setattr(
        signal_module,
        "write_wallet_flow_signal_report",
        fake_write_wallet_flow_signal_report,
    )
    monkeypatch.setattr(
        signal_module,
        "build_wallet_flow_rejection_diagnostics",
        fake_build_wallet_flow_rejection_diagnostics,
    )
    monkeypatch.setattr(
        triage_module,
        "write_wallet_flow_diagnostic_triage_report",
        fake_write_wallet_flow_diagnostic_triage_report,
    )
    from joint_research.research import wallet_flow_promotion_plan as promotion_module
    monkeypatch.setattr(
        promotion_module,
        "write_wallet_flow_promotion_plan_report",
        fake_write_wallet_flow_promotion_plan_report,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "research",
            "wallet-flow-signal",
            "--output-dir",
            str(tmp_path),
            "--diagnostic-report",
            "--promotion-plan",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in result.output
    assert calls["diagnostics"] == ["diagnostic"]
    assert (tmp_path / "wallet_flow_diagnostic_triage.md").exists()
    assert calls["triage_output_dir"] == tmp_path.resolve()
    assert calls["promotion_diagnostics"] == ["diagnostic"]
    assert calls["promotion_output_dir"] == tmp_path.resolve()
    assert (tmp_path / "wallet_flow_promotion_plan.md").exists()
